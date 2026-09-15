"""Simple SQLite-backed repository and job store for change-impact analysis.

Tables:
- workspaces(id INTEGER PK, name TEXT)
- repositories(id INTEGER PK, workspace_id INTEGER, name TEXT, git_url TEXT, local_path TEXT, branch TEXT)
- jobs(id TEXT PK, change TEXT, workspace_id INTEGER, status TEXT, result_json TEXT, created_at TEXT, updated_at TEXT)
"""

from __future__ import annotations

import os
import sqlite3
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

DB_PATH = os.environ.get("CHANGE_IMPACT_DB", "data/change_impact.db")


def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS repositories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER,
            name TEXT,
            git_url TEXT,
            local_path TEXT,
            branch TEXT
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            change TEXT,
            workspace_id INTEGER,
            status TEXT,
            result_json TEXT,
            created_at TEXT,
            updated_at TEXT
        )"""
    )
    conn.commit()
    conn.close()


def list_workspaces() -> List[Dict[str, Any]]:
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM workspaces")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def create_workspace(name: str) -> Dict[str, Any]:
    conn = _conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO workspaces(name) VALUES(?)", (name,))
    conn.commit()
    wid = cur.lastrowid
    conn.close()
    return {"id": wid, "name": name}


def list_repositories(workspace_id: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = _conn()
    cur = conn.cursor()
    if workspace_id:
        cur.execute("SELECT * FROM repositories WHERE workspace_id = ?", (workspace_id,))
    else:
        cur.execute("SELECT * FROM repositories")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def add_repository(workspace_id: int, name: str, git_url: Optional[str] = None, local_path: Optional[str] = None, branch: Optional[str] = None) -> Dict[str, Any]:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO repositories(workspace_id, name, git_url, local_path, branch) VALUES(?,?,?,?,?)",
        (workspace_id, name, git_url, local_path, branch)
    )
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return {"id": rid, "workspace_id": workspace_id, "name": name, "git_url": git_url, "local_path": local_path, "branch": branch}


def create_job(job_id: str, change: str, workspace_id: Optional[int]) -> None:
    conn = _conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute("INSERT INTO jobs(id, change, workspace_id, status, created_at, updated_at) VALUES(?,?,?,?,?,?)",
                (job_id, change, workspace_id, "pending", now, now))
    conn.commit()
    conn.close()


def update_job_status(job_id: str, status: str, result: Optional[Dict[str, Any]] = None) -> None:
    conn = _conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    result_json = json.dumps(result) if result is not None else None
    cur.execute("UPDATE jobs SET status = ?, result_json = ?, updated_at = ? WHERE id = ?",
                (status, result_json, now, job_id))
    conn.commit()
    conn.close()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    data = dict(row)
    if data.get("result_json"):
        data["result"] = json.loads(data["result_json"])
    else:
        data["result"] = None
    return data
