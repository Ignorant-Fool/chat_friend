"""记忆存储层：SQLite 持久化会话与消息历史。

提供会话（conversations）与消息（messages）两张表，
以及长期记忆（memories）表，用于跨会话记住用户偏好等信息。
所有操作线程安全，适合 FastAPI 多线程环境。
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '新对话',
    persona     TEXT NOT NULL DEFAULT 'buddy',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages (conversation_id, id);

CREATE TABLE IF NOT EXISTS memories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    key        TEXT NOT NULL UNIQUE,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """SQLite 记忆存储。

    示例::

        store = MemoryStore()
        cid = store.create_conversation(persona="buddy")
        store.add_message(cid, "user", "你好")
        history = store.get_history(cid)
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else Path(settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # 每个线程独立连接（sqlite3 连接不能跨线程共享）
        self._local = threading.local()
        if settings.auto_create_tables:
            self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            self._local.conn = conn
        return conn

    def init_db(self) -> None:
        conn = self._connect()
        conn.executescript(_SCHEMA)
        conn.commit()

    # ---------- 会话 ----------
    def create_conversation(self, persona: str = "buddy", title: str = "新对话") -> str:
        cid = uuid.uuid4().hex
        now = _now_iso()
        conn = self._connect()
        conn.execute(
            "INSERT INTO conversations (id, title, persona, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (cid, title, persona, now, now),
        )
        conn.commit()
        return cid

    def get_conversation(self, conversation_id: str) -> Optional[dict]:
        conn = self._connect()
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_conversations(self, limit: int = 100) -> list[dict]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def update_conversation_title(self, conversation_id: str, title: str) -> None:
        conn = self._connect()
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, _now_iso(), conversation_id),
        )
        conn.commit()

    def touch_conversation(self, conversation_id: str) -> None:
        conn = self._connect()
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (_now_iso(), conversation_id),
        )
        conn.commit()

    def delete_conversation(self, conversation_id: str) -> None:
        conn = self._connect()
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        conn.commit()

    # ---------- 消息 ----------
    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        conn = self._connect()
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, _now_iso()),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (_now_iso(), conversation_id),
        )
        conn.commit()

    def get_history(self, conversation_id: str, limit: int = 50) -> list[dict]:
        """按时间顺序返回最近的 limit 条消息（旧→新）。"""
        conn = self._connect()
        rows = conn.execute(
            "SELECT role, content FROM ("
            "  SELECT * FROM messages WHERE conversation_id = ? "
            "  ORDER BY id DESC LIMIT ?"
            ") ORDER BY id ASC",
            (conversation_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---------- 长期记忆 ----------
    def set_memory(self, key: str, value: str) -> None:
        conn = self._connect()
        conn.execute(
            "INSERT INTO memories (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            (key, value, _now_iso()),
        )
        conn.commit()

    def get_memory(self, key: str) -> Optional[str]:
        conn = self._connect()
        row = conn.execute(
            "SELECT value FROM memories WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def list_memories(self) -> list[dict]:
        conn = self._connect()
        rows = conn.execute("SELECT key, value, updated_at FROM memories").fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


# 进程级单例
_store: Optional[MemoryStore] = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
