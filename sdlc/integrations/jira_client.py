import re

import requests

from sdlc.config import JIRA_API_TOKEN, JIRA_BASE_URL, JIRA_EMAIL, JIRA_ISSUE_TYPE, JIRA_PROJECT_KEY


def _parse_stories(markdown: str) -> list[dict]:

    blocks = re.split(r"(?=^#{2,4}\s+(?:User\s+)?Story\s+\d+)", markdown, flags=re.MULTILINE | re.IGNORECASE)
    stories = []

    for block in blocks:
        block = block.strip()
        if not re.match(r"^#{2,4}\s+(?:User\s+)?Story\s+\d+", block, re.IGNORECASE):
            continue

        title_match = re.match(r"^#{2,4}\s+(?:User\s+)?Story\s+\d+\s*:?\s*([^\n]*)", block, re.IGNORECASE)
        title = (title_match.group(1).strip() if title_match else "") or "User Story"

        def read_field(label: str) -> str:
            match = re.search(rf"\*{{0,2}}{label}\*{{0,2}}\s*:?\s*([^\n]+)", block, re.IGNORECASE)
            return match.group(1).strip() if match else ""

        criteria_match = re.search(r"acceptance criteria(.*)", block, re.IGNORECASE | re.DOTALL)
        criteria_text = criteria_match.group(1).strip() if criteria_match else ""

        description = "\n".join(line for line in [
            f"As a {read_field('As a')}",
            f"I want {read_field('I want')}",
            f"So that {read_field('So that')}",
            "",
            "Acceptance Criteria:",
            criteria_text,
        ] if line)

        stories.append({"title": title, "description": description})

    return stories


def push_user_stories_to_jira(user_stories_markdown: str) -> list[dict]:

    if not (JIRA_BASE_URL and JIRA_EMAIL and JIRA_API_TOKEN and JIRA_PROJECT_KEY):
        raise ValueError(
            "JIRA is not configured. Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN and JIRA_PROJECT_KEY."
        )

    stories = _parse_stories(user_stories_markdown)
    if not stories:
        raise ValueError("No user stories could be parsed from the content.")

    created = []

    for story in stories:
        response = requests.post(
            f"{JIRA_BASE_URL.rstrip('/')}/rest/api/2/issue",
            json={
                "fields": {
                    "project": {"key": JIRA_PROJECT_KEY},
                    "summary": story["title"][:255],
                    "description": story["description"],
                    "issuetype": {"name": JIRA_ISSUE_TYPE},
                }
            },
            auth=(JIRA_EMAIL, JIRA_API_TOKEN),
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code >= 300:
            raise RuntimeError(f"Jira rejected '{story['title']}': {response.text}")

        key = response.json().get("key")
        created.append({
            "title": story["title"],
            "key": key,
            "url": f"{JIRA_BASE_URL.rstrip('/')}/browse/{key}",
        })

    return created
