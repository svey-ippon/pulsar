from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ThreadStore:
    """Conversation thread metadata (id, title, created_at) in a small sqlite table.

    The conversational state itself lives in the LangGraph checkpointer (same sqlite file,
    different tables) — this store only carries what the UI sidebar needs.
    """

    def __init__(self, db_path: str | Path):
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS threads ("
                " id TEXT PRIMARY KEY,"
                " title TEXT,"
                " created_at TEXT NOT NULL)"
            )
            self._conn.commit()

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, title, created_at FROM threads ORDER BY created_at DESC"
            ).fetchall()
        return [{"id": r[0], "title": r[1], "created_at": r[2]} for r in rows]

    def create(self) -> dict[str, Any]:
        thread = {
            "id": f"t-{uuid.uuid4().hex[:12]}",
            "title": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._conn.execute(
                "INSERT INTO threads (id, title, created_at) VALUES (?, ?, ?)",
                (thread["id"], thread["title"], thread["created_at"]),
            )
            self._conn.commit()
        return thread

    def get(self, thread_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, title, created_at FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()
        return {"id": row[0], "title": row[1], "created_at": row[2]} if row else None

    def delete(self, thread_id: str) -> bool:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            self._conn.commit()
        return cursor.rowcount > 0

    def set_title_if_empty(self, thread_id: str, title: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE threads SET title = ? WHERE id = ? AND title IS NULL",
                (title.strip()[:80], thread_id),
            )
            self._conn.commit()
