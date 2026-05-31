from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentMemoryStore:
    def __init__(self, db_path: str, max_entries_per_agent: int = 50) -> None:
        self._db_path = str(Path(db_path).resolve())
        self._max_entries = max(5, max_entries_per_agent)
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    run_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_memory_agent ON agent_memory(agent_id, id DESC)"
            )
            conn.commit()

    def append(
        self,
        *,
        agent_id: str,
        outcome: str,
        summary: str,
        detail: str,
        run_id: str | None = None,
    ) -> None:
        safe_summary = summary.strip()[:500]
        safe_detail = detail.strip()[:2000]
        if not safe_summary:
            return
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_memory(agent_id, outcome, summary, detail, run_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (agent_id, outcome, safe_summary, safe_detail, run_id, _utc_now_iso()),
            )
            conn.execute(
                """
                DELETE FROM agent_memory
                WHERE agent_id = ?
                  AND id NOT IN (
                    SELECT id FROM agent_memory
                    WHERE agent_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                  )
                """,
                (agent_id, agent_id, self._max_entries),
            )
            conn.commit()

    def get_context(self, agent_id: str, limit: int = 5) -> list[str]:
        safe_limit = max(1, min(limit, 20))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT outcome, summary, detail, created_at
                FROM agent_memory
                WHERE agent_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (agent_id, safe_limit),
            ).fetchall()
        lines: list[str] = []
        for row in reversed(rows):
            lines.append(
                f"[{row['created_at']}] {row['outcome']}: {row['summary']} — {row['detail'][:240]}"
            )
        return lines

    def list_entries(self, agent_id: str, limit: int = 20) -> list[dict[str, str]]:
        safe_limit = max(1, min(limit, 100))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, agent_id, outcome, summary, detail, run_id, created_at
                FROM agent_memory
                WHERE agent_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (agent_id, safe_limit),
            ).fetchall()
        return [dict(row) for row in rows]
