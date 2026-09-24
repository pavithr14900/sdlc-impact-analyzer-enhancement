"""Confluence Cloud v2 publishing for reviewed document snapshots."""
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

import markdown
import requests
from sdlc import config
from .document_pack import load_documents


def connection_status():
    fields = {name: getattr(config, name, "") for name in ("CONFLUENCE_BASE_URL", "CONFLUENCE_EMAIL", "CONFLUENCE_API_TOKEN", "CONFLUENCE_SPACE_KEY")}
    base = fields["CONFLUENCE_BASE_URL"].rstrip("/")
    parsed = urlsplit(base)
    valid = parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and parsed.path in ("", "/wiki")
    return {"configured": all(fields.values()) and valid, "baseUrl": base, "spaceKey": fields["CONFLUENCE_SPACE_KEY"],
            "parentPageId": config.CONFLUENCE_PARENT_PAGE_ID, "missing": [key for key, value in fields.items() if not value],
            "configurationError": "Use an HTTPS Confluence Cloud site URL, optionally ending in /wiki." if base and not valid else ""}


def _request(method, path, **kwargs):
    status = connection_status()
    if not status["configured"]:
        raise ValueError("Configure the Confluence connection on the backend before publishing.")
    base = status["baseUrl"].removesuffix("/wiki") + "/wiki/api/v2"
    try:
        response = requests.request(method, base + path, auth=(config.CONFLUENCE_EMAIL, config.CONFLUENCE_API_TOKEN),
                                    timeout=30, allow_redirects=False, **kwargs)
    except requests.RequestException as exc:
        raise RuntimeError("Confluence could not be reached. Check the connection and retry.") from exc
    if response.status_code >= 300:
        reasons = {401: "Authentication failed; check the backend email and API token.", 403: "The account does not have permission for this space or page.",
                   404: "The destination space or parent page was not found.", 409: "The page changed or its title conflicts. Refresh and retry.", 429: "Confluence rate limit reached; wait before retrying."}
        raise RuntimeError(reasons.get(response.status_code, f"Confluence rejected the request (HTTP {response.status_code})."))
    return response.json()


class StorageHTML(HTMLParser):
    """Keep only storage-compatible formatting, never active content from source/LLM text."""
    allowed = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "strong", "em", "code", "pre", "blockquote", "table", "thead", "tbody", "tr", "th", "td", "hr", "br", "a", "del"}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag not in self.allowed:
            return
        attributes = ""
        if tag == "a":
            href = dict(attrs).get("href", "")
            if urlsplit(href).scheme in ("https", "http", "mailto") or href.startswith("#"):
                attributes = f' href="{escape(href, quote=True)}"'
        self.parts.append(f"<{tag}{attributes}{' /' if tag in ('br', 'hr') else ''}>")
    def handle_endtag(self, tag):
        if tag in self.allowed and tag not in ("br", "hr"):
            self.parts.append(f"</{tag}>")
    def handle_data(self, data):
        self.parts.append(escape(data))


def storage_body(content):
    parser = StorageHTML()
    parser.feed(markdown.markdown(content, extensions=["tables", "fenced_code"]))
    return ''.join(parser.parts)


def publish_documents(analysis, selections):
    status = connection_status()
    if not status["configured"]:
        raise ValueError("Confluence is not configured. Complete the backend connection settings first.")
    documents = load_documents(analysis["analysisId"], [item["type"] for item in selections])
    revisions = {item["type"]: item["revision"] for item in selections}
    if any(doc["revision"] != revisions[doc["type"]] for doc in documents):
        raise ValueError("A selected document has changed. Reload the generated documents and review them before publishing.")
    spaces = _request("GET", "/spaces", params={"keys": status["spaceKey"], "limit": 1}).get("results", [])
    if not spaces:
        raise ValueError("The configured Confluence space could not be found.")
    space_id = str(spaces[0]["id"])
    parent = status["parentPageId"]
    if parent:
        if not str(parent).isdigit():
            raise ValueError("The configured parent page ID must be numeric.")
        page = _request("GET", f"/pages/{parent}")
        if str(page.get("spaceId")) != space_id:
            raise ValueError("The configured parent page belongs to a different space.")
    published, errors = [], []
    for doc in documents:
        # Analysis-specific titles keep unrelated application documentation separate.
        title = f"{str(analysis.get('name') or 'Application')[:100]} ? {doc['title']} [{analysis['analysisId']}]"
        try:
            existing = _request("GET", "/pages", params={"space-id": space_id, "title": title, "status": "current", "limit": 2}).get("results", [])
            payload = {"spaceId": space_id, "status": "current", "title": title, "body": {"representation": "storage", "value": storage_body(doc["content"])}}
            if existing:
                current = _request("GET", f"/pages/{existing[0]['id']}")
                if parent and str(current.get("parentId")) != str(parent):
                    raise ValueError("A matching page exists under another parent. Resolve the destination conflict before publishing.")
                payload.update(id=current["id"], version={"number": current["version"]["number"] + 1, "message": "Updated from reviewed BuildPilot documentation"})
                result = _request("PUT", f"/pages/{current['id']}", json=payload)
                action = "updated"
            else:
                if parent:
                    payload["parentId"] = str(parent)
                result = _request("POST", "/pages", json=payload)
                action = "created"
            published.append({"type": doc["type"], "title": title, "action": action,
                "url": status["baseUrl"].removesuffix("/wiki") + "/wiki/pages/viewpage.action?pageId=" + str(result["id"])})
        except (RuntimeError, ValueError) as exc:
            errors.append({"type": doc["type"], "title": title, "error": str(exc)})
    return {"pages": published, "errors": errors}
