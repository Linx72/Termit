from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _token_overlap_score(left: str, right: str) -> float:
    tokens_left = {token for token in re.findall(r"\w+", left.lower()) if len(token) > 2}
    tokens_right = {token for token in re.findall(r"\w+", right.lower()) if len(token) > 2}
    if not tokens_left or not tokens_right:
        return 0.0
    return len(tokens_left & tokens_right) / len(tokens_left)


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
        with closing(self._connect()) as conn:
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
            self._ensure_column(conn, "agent_memory", "workspace_scope", "TEXT")
            conn.commit()

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {row[1] for row in rows}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def append(
        self,
        *,
        agent_id: str,
        outcome: str,
        summary: str,
        detail: str,
        run_id: str | None = None,
        workspace_scope: str | None = None,
    ) -> None:
        safe_summary = summary.strip()[:500]
        safe_detail = detail.strip()[:2000]
        safe_scope = (workspace_scope or "").strip()[:200] or None
        if not safe_summary:
            return
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO agent_memory(agent_id, outcome, summary, detail, run_id, created_at, workspace_scope)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (agent_id, outcome, safe_summary, safe_detail, run_id, _utc_now_iso(), safe_scope),
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

    def get_context(
        self,
        agent_id: str,
        limit: int = 5,
        workspace_scope: str | None = None,
    ) -> list[str]:
        safe_limit = max(1, min(limit, 20))
        scope = (workspace_scope or "").strip()
        with self._lock, closing(self._connect()) as conn:
            if scope:
                rows = conn.execute(
                    """
                    SELECT outcome, summary, detail, created_at
                    FROM agent_memory
                    WHERE agent_id = ?
                      AND (workspace_scope IS NULL OR workspace_scope = '' OR workspace_scope = ?)
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (agent_id, scope, safe_limit),
                ).fetchall()
            else:
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

    def get_context_for_task(
        self,
        agent_id: str,
        task_hint: str,
        limit: int = 5,
        workspace_scope: str | None = None,
    ) -> list[str]:
        """Релевантные воспоминания: overlap по task_hint, fallback на recency."""
        hint = task_hint.strip()
        if not hint:
            return self.get_context(agent_id, limit=limit, workspace_scope=workspace_scope)

        safe_limit = max(1, min(limit, 20))
        pool_limit = min(self._max_entries, max(safe_limit * 4, 20))
        scope = (workspace_scope or "").strip()
        with self._lock, closing(self._connect()) as conn:
            if scope:
                rows = conn.execute(
                    """
                    SELECT id, outcome, summary, detail, created_at
                    FROM agent_memory
                    WHERE agent_id = ?
                      AND (workspace_scope IS NULL OR workspace_scope = '' OR workspace_scope = ?)
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (agent_id, scope, pool_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, outcome, summary, detail, created_at
                    FROM agent_memory
                    WHERE agent_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (agent_id, pool_limit),
                ).fetchall()

        scored: list[tuple[float, int, sqlite3.Row]] = []
        for row in rows:
            blob = f"{row['summary']} {row['detail']}"
            score = _token_overlap_score(hint, blob)
            scored.append((score, int(row["id"]), row))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        selected = scored[:safe_limit]
        # Хронологический порядок в prompt (старые → новые).
        selected.sort(key=lambda item: item[1])

        lines: list[str] = []
        for score, _row_id, row in selected:
            relevance = f"relevance={score:.2f} " if score > 0 else ""
            lines.append(
                f"[{row['created_at']}] {relevance}{row['outcome']}: {row['summary']} — {row['detail'][:240]}"
            )
        return lines

    def list_entries(self, agent_id: str, limit: int = 20) -> list[dict[str, str]]:
        safe_limit = max(1, min(limit, 100))
        with self._lock, closing(self._connect()) as conn:
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
