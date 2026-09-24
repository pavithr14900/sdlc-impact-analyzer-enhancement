"""SQLite analysis snapshots, including progress and evidence, independent of impact jobs."""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import threading
import uuid

DB_PATH = os.getenv("LEGACY_INTELLIGENCE_DB", "data/legacy_intelligence.db")
# Persist a session id on disk so a simple backend restart does not change
# ownership and automatically fail in-progress analyses. This keeps the
# existing behaviour for multi-process installs but avoids false failures
# for a single local backend that is restarted during development.
_session_file_env = os.getenv("LEGACY_INTELLIGENCE_SESSION_FILE", "")

def _load_or_create_session(db_path: str) -> str:
    base = Path(db_path).resolve().parent
    base.mkdir(parents=True, exist_ok=True)
    session_file = Path(_session_file_env) if _session_file_env else base / "legacy_intelligence.session"
    try:
        if session_file.exists():
            return session_file.read_text(encoding="utf-8").strip() or uuid.uuid4().hex
        sid = uuid.uuid4().hex
        session_file.write_text(sid, encoding="utf-8")
        return sid
    except Exception:
        # Fall back to in-memory session if file operations are not permitted.
        return uuid.uuid4().hex

SESSION = _load_or_create_session(DB_PATH)
_initialized: set[str] = set()
_lock = threading.RLock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect():
    path = str(Path(DB_PATH).resolve())
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    with _lock:
        if path not in _initialized:
            connection.execute("CREATE TABLE IF NOT EXISTS legacy_analyses (id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, payload TEXT NOT NULL, owner TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS legacy_deleted_analyses (id TEXT PRIMARY KEY)")
            # BuildPilot runs one local backend process. Persisted work cannot survive its restart.
            rows = connection.execute("SELECT id, payload FROM legacy_analyses WHERE owner != ?", (SESSION,)).fetchall()
            for row in rows:
                value = json.loads(row["payload"])
                if value["status"] not in {"COMPLETED", "FAILED"}:
                    value.update(status="FAILED", error="The backend restarted before this analysis finished. Start a new analysis.", updatedAt=now())
                    connection.execute("UPDATE legacy_analyses SET payload = ?, updated_at = ? WHERE id = ?", (json.dumps(value), value["updatedAt"], row["id"]))
            connection.commit()
            _initialized.add(path)
    return connection


def save(analysis: dict) -> dict | None:
    analysis["updatedAt"] = now()
    with _lock, closing(_connect()) as connection:
        if connection.execute("SELECT 1 FROM legacy_deleted_analyses WHERE id = ?", (analysis["analysisId"],)).fetchone():
            return None
        connection.execute("INSERT INTO legacy_analyses(id, updated_at, payload, owner) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at,payload=excluded.payload,owner=excluded.owner", (analysis["analysisId"], analysis["updatedAt"], json.dumps(analysis), SESSION))
        connection.commit()
    return analysis


def delete(analysis_id: str) -> bool:
    """Remove the snapshot; retain only its ID to prevent a worker resurrecting it."""
    with _lock, closing(_connect()) as connection:
        with connection:
            cursor = connection.execute("DELETE FROM legacy_analyses WHERE id = ?", (analysis_id,))
            if not cursor.rowcount:
                return False
            connection.execute("INSERT OR IGNORE INTO legacy_deleted_analyses(id) VALUES(?)", (analysis_id,))
    return True


def get(analysis_id: str) -> dict | None:
    with closing(_connect()) as connection:
        row = connection.execute("SELECT payload FROM legacy_analyses WHERE id = ?", (analysis_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def recent(limit: int = 30) -> list[dict]:
    with closing(_connect()) as connection:
        rows = connection.execute("SELECT payload FROM legacy_analyses ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    keys = ("analysisId", "name", "repositories", "status", "createdAt", "updatedAt", "progress", "engine", "error")
    return [{key: value.get(key) for key in keys} for value in (json.loads(row["payload"]) for row in rows)]
