"""Bounded retrieval of design documentation, preserving main content and sources."""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urldefrag

from sdlc.rag.knowledge_base import _extract_text


class GuidanceParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []
        self.main_parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(tag)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in {"p", "li", "pre", "br", "h1", "h2", "h3", "h4", "tr"}:
            self.handle_data("\n")

    def handle_endtag(self, tag):
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]

    def handle_data(self, data):
        if any(tag in self.stack for tag in ("script", "style", "nav", "footer", "header", "noscript")):
            return
        self.parts.append(data)
        if "main" in self.stack or "article" in self.stack:
            self.main_parts.append(data)

    @property
    def text(self):
        return "\n".join(" ".join(line.split()) for line in " ".join(self.main_parts or self.parts).splitlines() if line.strip())


def fetch_guidance(url, max_pages=12):
    import requests

    if urlparse(url).scheme not in {"http", "https"} or not urlparse(url).hostname:
        raise ValueError("Supply an HTTP or HTTPS URL.")
    documents, warnings, visited = [], [], set()
    queue = [url]
    origin = None
    topics = ("colour", "color", "typograph", "typeface", "type-scale", "spacing", "layout", "page-template", "button", "text-input", "focus", "accessib", "font", "design-token")
    with requests.Session() as session:
        session.headers["User-Agent"] = "BuildPilot/1.0 (design guidance retrieval)"
        while queue and len(visited) < max_pages:
            target = queue.pop(0)
            if target in visited:
                continue
            visited.add(target)
            try:
                with session.get(target, timeout=(5, 15), stream=True) as response:
                    response.raise_for_status()
                    if origin is None:
                        origin = urlparse(response.url).netloc
                    elif urlparse(response.url).netloc != origin:
                        raise ValueError("Linked page redirected outside the documentation site")
                    body = bytearray()
                    for chunk in response.iter_content(8192):
                        body.extend(chunk)
                        if len(body) > 2_500_000:
                            raise ValueError("Page exceeds the 2.5 MB limit")
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "pdf" in content_type or urlparse(target).path.endswith(".pdf"):
                        content = _extract_text("guidance.pdf", bytes(body))
                    elif "html" in content_type:
                        parser = GuidanceParser()
                        parser.feed(bytes(body).decode(response.encoding or "utf-8", errors="replace"))
                        content = parser.text
                        links = [urldefrag(urljoin(response.url, href))[0] for href in parser.links]
                        for link in links:
                            parsed = urlparse(link)
                            if parsed.scheme in {"http", "https"} and parsed.netloc == origin and not parsed.query and any(topic in parsed.path.lower() for topic in topics) and link not in visited and link not in queue:
                                queue.append(link)
                        # Fetch concrete foundations before less specific overview pages.
                        queue.sort(key=lambda link: next((index for index, topic in enumerate(topics) if topic in urlparse(link).path.lower()), len(topics)))
                    else:
                        content = bytes(body).decode("utf-8", errors="replace")
                    if len(content.strip()) < 80:
                        raise ValueError("No useful guidance text found; the page may require JavaScript or authentication")
                    documents.append((response.url, content))
            except Exception as exc:
                if not documents:
                    raise
                warnings.append(f"Could not retrieve {target}: {exc}")
    if queue:
        warnings.append(f"Retrieval limited to {max_pages} pages; additional linked guidance was not fetched.")
    return documents, warnings
