"""T.A.R.O. - Tier 1 Short-Term Memory (SQLite).

ARCHITECTURE reference: section 12.
MEMORY reference: section 3 (Tier 1).
TASKS: TASK-060.

Stores sessions, conversation turns, tool call records, and rolling summaries.
Retention: default 90 days.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from core.log.setup import get_logger

logger = get_logger(__name__)


@dataclass
class TurnRecord:
    id: str
    session_id: str
    role: str
    content: str
    created_at: str
    tokens: int = 0


@dataclass
class ToolCallRecord:
    id: str
    turn_id: str
    tool: str
    args_masked: dict[str, Any]
    status: str
    output_ref: str
    duration_ms: int


@dataclass
class SummaryRecord:
    id: str
    session_id: str
    text: str
    covers_turns: int
    created_at: str


class SQLiteMemoryStore:
    """Tier 1 SQLite storage for sessions, turns, tool calls, and summaries."""

    def __init__(self, db_path: Path | str = "data/taro.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        """Create tables if not existing."""
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turns (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    tokens INTEGER DEFAULT 0,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id TEXT PRIMARY KEY,
                    turn_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    args_masked TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output_ref TEXT,
                    duration_ms INTEGER DEFAULT 0,
                    FOREIGN KEY(turn_id) REFERENCES turns(id)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    covers_turns INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    turn_id TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY(turn_id) REFERENCES turns(id)
                )
                """
            )

    def start_session(self, session_id: str) -> None:
        """Record start of a new session."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO sessions (id, started_at) VALUES (?, ?)",
                (session_id, now),
            )

    def add_turn(
        self,
        turn_id: str,
        session_id: str,
        role: str,
        content: str,
        tokens: int = 0,
    ) -> None:
        """Insert a conversation turn."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO turns (id, session_id, role, content, created_at, tokens)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (turn_id, session_id, role, content, now, tokens),
            )

    def get_recent_turns(self, session_id: str, limit: int = 20) -> list[TurnRecord]:
        """Fetch newest turns in chronological order."""
        cur = self._conn.execute(
            """
            SELECT id, session_id, role, content, created_at, tokens
            FROM turns
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        )
        rows = cur.fetchall()
        # Reverse to return oldest-to-newest within the window
        records = [
            TurnRecord(
                id=r["id"],
                session_id=r["session_id"],
                role=r["role"],
                content=r["content"],
                created_at=r["created_at"],
                tokens=r["tokens"],
            )
            for r in reversed(rows)
        ]
        return records

    def add_summary(
        self,
        summary_id: str,
        session_id: str,
        text: str,
        covers_turns: int,
    ) -> None:
        """Store a rolling summary."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO summaries (id, session_id, text, covers_turns, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (summary_id, session_id, text, covers_turns, now),
            )

    def get_latest_summary(self, session_id: str) -> SummaryRecord | None:
        """Get the most recent summary for a session."""
        cur = self._conn.execute(
            """
            SELECT id, session_id, text, covers_turns, created_at
            FROM summaries
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (session_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return SummaryRecord(
            id=row["id"],
            session_id=row["session_id"],
            text=row["text"],
            covers_turns=row["covers_turns"],
            created_at=row["created_at"],
        )

    def purge_old_data(self, retention_days: int = 90) -> int:
        """Purge sessions and turns older than retention days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        with self._conn:
            cur = self._conn.execute(
                "DELETE FROM turns WHERE created_at < ?",
                (cutoff,),
            )
            return cur.rowcount

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()


# Singleton instance
_sqlite_store: SQLiteMemoryStore | None = None


def get_sqlite_store(path: Path | str | None = None) -> SQLiteMemoryStore:
    """Return singleton SQLite store."""
    global _sqlite_store
    if _sqlite_store is None or path is not None:
        _sqlite_store = SQLiteMemoryStore(path or "data/taro.db")
    return _sqlite_store
