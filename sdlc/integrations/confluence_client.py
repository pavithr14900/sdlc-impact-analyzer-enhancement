import os

import markdown as md_lib
import requests

from sdlc.config import (
    CONFLUENCE_API_TOKEN,
    CONFLUENCE_BASE_URL,
    CONFLUENCE_EMAIL,
    CONFLUENCE_PARENT_PAGE_ID,
    CONFLUENCE_SPACE_KEY,
)


def _find_existing_page(title: str):

    response = requests.get(
        f"{CONFLUENCE_BASE_URL.rstrip('/')}/wiki/rest/api/content",
        params={"title": title, "spaceKey": CONFLUENCE_SPACE_KEY, "expand": "version"},
        auth=(CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN),
        timeout=30,
    )
    response.raise_for_status()
    results = response.json().get("results", [])

    return results[0] if results else None


def _publish_page(title: str, html_body: str) -> dict:

    existing = _find_existing_page(title)
    base_url = f"{CONFLUENCE_BASE_URL.rstrip('/')}/wiki/rest/api/content"
    auth = (CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN)

    if existing:
        payload = {
            "id": existing["id"],
            "type": "page",
            "title": title,
            "space": {"key": CONFLUENCE_SPACE_KEY},
            "body": {"storage": {"value": html_body, "representation": "storage"}},
            "version": {"number": existing["version"]["number"] + 1},
        }
        response = requests.put(f"{base_url}/{existing['id']}", json=payload, auth=auth, timeout=30)
    else:
        payload = {
            "type": "page",
            "title": title,
            "space": {"key": CONFLUENCE_SPACE_KEY},
            "body": {"storage": {"value": html_body, "representation": "storage"}},
        }
        if CONFLUENCE_PARENT_PAGE_ID:
            payload["ancestors"] = [{"id": CONFLUENCE_PARENT_PAGE_ID}]
        response = requests.post(base_url, json=payload, auth=auth, timeout=30)

    if response.status_code >= 300:
        raise RuntimeError(f"Confluence rejected '{title}': {response.text}")

    data = response.json()

    return {"title": title, "url": f"{CONFLUENCE_BASE_URL.rstrip('/')}/wiki{data['_links']['webui']}"}


def publish_documentation_to_confluence(docs_dir: str) -> list[dict]:

    if not (CONFLUENCE_BASE_URL and CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN and CONFLUENCE_SPACE_KEY):
        raise ValueError(
            "Confluence is not configured. Set CONFLUENCE_BASE_URL, CONFLUENCE_EMAIL, "
            "CONFLUENCE_API_TOKEN and CONFLUENCE_SPACE_KEY."
        )

    if not os.path.isdir(docs_dir):
        raise ValueError("No documentation has been generated yet.")

    published = []

    for filename in sorted(os.listdir(docs_dir)):
        if not filename.lower().endswith(".md"):
            continue

        with open(os.path.join(docs_dir, filename), "r", encoding="utf-8") as file:
            content = file.read()

        title_line = content.splitlines()[0].lstrip("#").strip() if content.strip() else filename
        html_body = md_lib.markdown(content, extensions=["tables", "fenced_code"])
        published.append(_publish_page(title_line, html_body))

    if not published:
        raise ValueError(
            "No markdown documentation files were found to publish. Re-run the Documentation "
            "stage so source .md files exist alongside the PDFs."
        )

    return published
