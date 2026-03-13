from __future__ import annotations

import json
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional, Any

from app.auth.firebase_admin import get_firestore_client
from app.models.assistant_models import AssistantMode, MemoryMessage
from app.services.google_calendar_service import GoogleCalendarService


class MemoryService:
    """Firestore-first память ассистента с SQLite fallback и локальным cache."""

    def __init__(self, db_path: str = "assistant_memory.db") -> None:
        self.db_path = str(Path(db_path))
        self.calendar_service = GoogleCalendarService()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS assistant_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    mode TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS assistant_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, session_id, mode)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS assistant_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS assistant_pending_actions (
                    confirmation_token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _fs(self):
        try:
            return get_firestore_client()
        except Exception:
            return None

    def add_message(self, user_id: str, role: str, content: str, mode: AssistantMode, session_id: Optional[str] = None) -> None:
        now_iso = datetime.now(UTC).isoformat()
        fs = self._fs()
        if fs is not None:
            try:
                fs.collection("assistant_messages").add({
                    "user_id": user_id,
                    "session_id": session_id,
                    "mode": mode.value,
                    "role": role,
                    "content": content,
                    "created_at": now_iso,
                })
            except Exception:
                pass
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO assistant_messages (user_id, session_id, mode, role, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, session_id, mode.value, role, content, now_iso),
            )

    def get_context(self, user_id: str, limit: int = 10, session_id: Optional[str] = None, mode: AssistantMode = AssistantMode.QUICK) -> list[MemoryMessage]:
        fs = self._fs()
        if fs is not None:
            try:
                query = fs.collection("assistant_messages").where("user_id", "==", user_id).where("mode", "==", mode.value)
                docs = list(query.stream())
                if session_id:
                    docs = [d for d in docs if d.to_dict().get("session_id") == session_id]
                docs = sorted(docs, key=lambda d: d.to_dict().get("created_at") or "")[-limit:]
                return [
                    MemoryMessage(
                        role=d.to_dict().get("role", "assistant"),
                        content=d.to_dict().get("content", ""),
                        created_at=d.to_dict().get("created_at"),
                        mode=AssistantMode(d.to_dict().get("mode", mode.value)),
                    )
                    for d in docs
                ]
            except Exception:
                pass

        query = "SELECT role, content, created_at, mode FROM assistant_messages WHERE user_id = ? AND mode = ? "
        params: list[Any] = [user_id, mode.value]
        if session_id:
            query += "AND session_id = ? "
            params.append(session_id)
        query += "ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [MemoryMessage(role=row["role"], content=row["content"], created_at=row["created_at"], mode=AssistantMode(row["mode"])) for row in reversed(rows)]

    def get_summary(self, user_id: str, session_id: str, mode: AssistantMode) -> Optional[str]:
        fs = self._fs()
        if fs is not None:
            try:
                doc = fs.collection("assistant_summaries").document(f"{user_id}:{session_id}:{mode.value}").get()
                if doc.exists:
                    return (doc.to_dict() or {}).get("summary")
            except Exception:
                pass
        with self._connect() as conn:
            row = conn.execute(
                "SELECT summary FROM assistant_summaries WHERE user_id = ? AND session_id = ? AND mode = ?",
                (user_id, session_id, mode.value),
            ).fetchone()
        return row["summary"] if row else None

    def upsert_summary(self, user_id: str, session_id: str, mode: AssistantMode, summary: str) -> None:
        now_iso = datetime.now(UTC).isoformat()
        fs = self._fs()
        if fs is not None:
            try:
                fs.collection("assistant_summaries").document(f"{user_id}:{session_id}:{mode.value}").set({
                    "user_id": user_id,
                    "session_id": session_id,
                    "mode": mode.value,
                    "summary": summary,
                    "updated_at": now_iso,
                })
            except Exception:
                pass
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO assistant_summaries (user_id, session_id, mode, summary, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, session_id, mode)
                DO UPDATE SET summary = excluded.summary, updated_at = excluded.updated_at
                """,
                (user_id, session_id, mode.value, summary, now_iso),
            )

    def get_cached_response(self, cache_key: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM assistant_cache WHERE cache_key = ?", (cache_key,)).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["payload"])
        except Exception:
            return None

    def set_cached_response(self, cache_key: str, payload: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO assistant_cache (cache_key, payload, created_at) VALUES (?, ?, ?)",
                (cache_key, json.dumps(payload, ensure_ascii=False), datetime.now(UTC).isoformat()),
            )

    def save_pending_action(self, confirmation_token: str, user_id: str, payload: dict, session_id: Optional[str] = None) -> None:
        now_iso = datetime.now(UTC).isoformat()
        fs = self._fs()
        if fs is not None:
            try:
                fs.collection("assistant_pending_actions").document(confirmation_token).set({
                    "user_id": user_id,
                    "session_id": session_id,
                    "payload": payload,
                    "created_at": now_iso,
                })
            except Exception:
                pass
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO assistant_pending_actions (confirmation_token, user_id, session_id, payload, created_at) VALUES (?, ?, ?, ?, ?)",
                (confirmation_token, user_id, session_id, json.dumps(payload, ensure_ascii=False), now_iso),
            )

    def get_pending_action(self, confirmation_token: str, user_id: str) -> Optional[dict]:
        fs = self._fs()
        if fs is not None:
            try:
                doc = fs.collection("assistant_pending_actions").document(confirmation_token).get()
                if doc.exists:
                    data = doc.to_dict() or {}
                    if str(data.get("user_id")) == str(user_id):
                        return data.get("payload")
            except Exception:
                pass
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM assistant_pending_actions WHERE confirmation_token = ? AND user_id = ?",
                (confirmation_token, user_id),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["payload"])
        except Exception:
            return None

    def delete_pending_action(self, confirmation_token: str) -> None:
        fs = self._fs()
        if fs is not None:
            try:
                fs.collection("assistant_pending_actions").document(confirmation_token).delete()
            except Exception:
                pass
        with self._connect() as conn:
            conn.execute("DELETE FROM assistant_pending_actions WHERE confirmation_token = ?", (confirmation_token,))

    def get_user_calendar(self, user_id: str, date_from=None, date_to=None):
        return self.calendar_service.list_events(date_from=date_from, date_to=date_to)

    def create_event(self, user_id: str, event_data: dict):
        result = self.calendar_service.create_event(event_data)
        result["user_id"] = user_id
        return result

    def set_reminder(self, user_id: str, reminder_data: dict):
        return {"user_id": user_id, "created": True, "reminder": reminder_data, "source": "app_memory"}
