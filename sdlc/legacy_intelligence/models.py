"""Validated API inputs and shared evidence records."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal
from urllib.parse import urlsplit

from sdlc.services.change_impact_service import validate_local_path

STATUSES = {"NOT_STARTED", "SCANNING", "INDEXING", "ANALYZING", "COMPLETED", "FAILED"}


@dataclass(frozen=True)
class Evidence:
    id: str
    repository: str
    file: str
    symbol: str
    lineStart: int
    lineEnd: int
    evidenceType: Literal["CODE", "CONFIGURATION", "DATABASE", "API", "TEST", "COMMENT"] = "CODE"
    snippet: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def validate_repositories(payload) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    repositories = payload.get("repositories")
    if not isinstance(repositories, list) or not 1 <= len(repositories) <= 5:
        raise ValueError("Provide between one and five repositories.")
    result, seen = [], set()
    for entry in repositories:
        if not isinstance(entry, dict):
            raise ValueError("Each repository must be an object with type and path or URL.")
        if entry.get("type") == "local":
            path = validate_local_path(entry.get("path"))
            item = {"type": "local", "path": path}
            identity = ("local", path.casefold())
        elif entry.get("type") == "git":
            url = entry.get("url")
            if not isinstance(url, str) or not url.strip() or len(url) > 2048:
                raise ValueError("Enter a valid Git repository HTTPS URL.")
            url = url.strip()
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or not parsed.path.strip("/"):
                raise ValueError("Git repositories require an HTTPS URL with a repository path.")
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("Use a Git URL without embedded credentials, query parameters or fragments; configure Git credentials on the backend.")
            item = {"type": "git", "url": url}
            identity = ("git", url.rstrip("/"))
        else:
            raise ValueError("Repository type must be local or git.")
        if identity not in seen:
            result.append(item)
            seen.add(identity)
    return result


def progress(step: int, message: str) -> dict:
    return {"step": step, "totalSteps": 8, "message": message, "percent": round(step / 8 * 100)}
