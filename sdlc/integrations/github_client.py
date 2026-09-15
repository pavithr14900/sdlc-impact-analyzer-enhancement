import base64
import os

import requests

from sdlc.config import GITHUB_BRANCH, GITHUB_REPO, GITHUB_TOKEN

_API_BASE = "https://api.github.com"


def _headers() -> dict:

    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }


def _collect_files(root: str) -> list[tuple[str, str]]:

    files = []

    for current_dir, _dirs, filenames in os.walk(root):
        for filename in filenames:
            full_path = os.path.join(current_dir, filename)
            relative_path = os.path.relpath(full_path, root).replace("\\", "/")
            files.append((relative_path, full_path))

    return files


def commit_generated_code_to_github(source_dir: str, commit_message: str) -> dict:

    if not (GITHUB_TOKEN and GITHUB_REPO):
        raise ValueError("GitHub is not configured. Set GITHUB_TOKEN and GITHUB_REPO (owner/repo).")

    if not os.path.isdir(source_dir):
        raise ValueError("No generated code found to commit.")

    files = _collect_files(source_dir)
    if not files:
        raise ValueError("No generated files found to commit.")

    repo_url = f"{_API_BASE}/repos/{GITHUB_REPO}"

    ref_response = requests.get(f"{repo_url}/git/ref/heads/{GITHUB_BRANCH}", headers=_headers(), timeout=30)
    if ref_response.status_code >= 300:
        raise RuntimeError(f"Could not read branch '{GITHUB_BRANCH}': {ref_response.text}")
    base_commit_sha = ref_response.json()["object"]["sha"]

    commit_response = requests.get(f"{repo_url}/git/commits/{base_commit_sha}", headers=_headers(), timeout=30)
    commit_response.raise_for_status()
    base_tree_sha = commit_response.json()["tree"]["sha"]

    tree_entries = []

    for relative_path, full_path in files:

        with open(full_path, "rb") as file:
            content_bytes = file.read()

        blob_response = requests.post(
            f"{repo_url}/git/blobs",
            json={"content": base64.b64encode(content_bytes).decode("ascii"), "encoding": "base64"},
            headers=_headers(),
            timeout=30,
        )
        blob_response.raise_for_status()

        tree_entries.append({
            "path": relative_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob_response.json()["sha"],
        })

    tree_response = requests.post(
        f"{repo_url}/git/trees",
        json={"base_tree": base_tree_sha, "tree": tree_entries},
        headers=_headers(),
        timeout=30,
    )
    tree_response.raise_for_status()

    new_commit_response = requests.post(
        f"{repo_url}/git/commits",
        json={
            "message": commit_message,
            "tree": tree_response.json()["sha"],
            "parents": [base_commit_sha],
        },
        headers=_headers(),
        timeout=30,
    )
    new_commit_response.raise_for_status()
    new_commit_sha = new_commit_response.json()["sha"]

    update_ref_response = requests.patch(
        f"{repo_url}/git/refs/heads/{GITHUB_BRANCH}",
        json={"sha": new_commit_sha},
        headers=_headers(),
        timeout=30,
    )
    if update_ref_response.status_code >= 300:
        raise RuntimeError(f"Could not update branch '{GITHUB_BRANCH}': {update_ref_response.text}")

    return {
        "commit_sha": new_commit_sha,
        "file_count": len(files),
        "url": f"https://github.com/{GITHUB_REPO}/commit/{new_commit_sha}",
    }
