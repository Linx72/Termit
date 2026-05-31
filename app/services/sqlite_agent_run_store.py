from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock
from typing import Optional

from app.domain.schemas import AgentRunEvent, AgentRunRecordResponse, AgentRunState


class SQLiteAgentRunStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = str(Path(db_path).resolve())
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    input TEXT NOT NULL,
                    session_id TEXT,
                    provider TEXT,
                    model TEXT,
                    attempts INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    failure_class TEXT,
                    attempted_models TEXT NOT NULL,
                    response TEXT NOT NULL,
                    error TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_updated ON agent_runs(agent_id, updated_at DESC)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_updated ON agent_runs(updated_at DESC)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    attempt INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_run_events_run_id ON agent_run_events(run_id, id)"
            )
            self._ensure_column(conn, "agent_runs", "attempts", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "agent_runs", "max_attempts", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(conn, "agent_runs", "failure_class", "TEXT")
            conn.commit()

    def put_run(self, run: AgentRunRecordResponse) -> None:
        with self._lock, self._connect() as conn:
            attempted = "\n".join(run.attempted_models)
            conn.execute(
                """
                INSERT INTO agent_runs(
                    run_id, agent_id, agent_name, state, created_at, updated_at,
                    input, session_id, provider, model, attempts, max_attempts, failure_class,
                    attempted_models, response, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    agent_id=excluded.agent_id,
                    agent_name=excluded.agent_name,
                    state=excluded.state,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    input=excluded.input,
                    session_id=excluded.session_id,
                    provider=excluded.provider,
                    model=excluded.model,
                    attempts=excluded.attempts,
                    max_attempts=excluded.max_attempts,
                    failure_class=excluded.failure_class,
                    attempted_models=excluded.attempted_models,
                    response=excluded.response,
                    error=excluded.error
                """,
                (
                    run.run_id,
                    run.agent_id,
                    run.agent_name,
                    run.state.value,
                    run.created_at,
                    run.updated_at,
                    run.input,
                    run.session_id,
                    run.provider,
                    run.model,
                    run.attempts,
                    run.max_attempts,
                    run.failure_class,
                    attempted,
                    run.response,
                    run.error,
                ),
            )
            conn.commit()

    def get_run(self, run_id: str) -> Optional[AgentRunRecordResponse]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    def list_runs(self, limit: int = 50) -> list[AgentRunRecordResponse]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_runs ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def list_runs_by_agent(self, agent_id: str, limit: int = 50) -> list[AgentRunRecordResponse]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_runs WHERE agent_id = ? ORDER BY updated_at DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def append_event(self, run_id: str, event: AgentRunEvent) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_run_events(run_id, event_type, state, message, timestamp, attempt)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    event.event_type,
                    event.state.value,
                    event.message,
                    event.timestamp,
                    event.attempt,
                ),
            )
            conn.commit()

    def get_events(self, run_id: str, limit: int = 500) -> list[AgentRunEvent]:
        safe_limit = max(1, min(limit, 2000))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT event_type, state, message, timestamp, attempt
                FROM agent_run_events
                WHERE run_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (run_id, safe_limit),
            ).fetchall()
        return [
            AgentRunEvent(
                event_type=row["event_type"],
                state=AgentRunState(row["state"]),
                message=row["message"],
                timestamp=row["timestamp"],
                attempt=row["attempt"],
            )
            for row in rows
        ]

    def trim_events(self, run_id: str, max_events: int) -> int:
        safe_max = max(1, max_events)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM agent_run_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            total = int(row["c"] if row else 0)
            if total <= safe_max:
                return 0
            keep_from_id_row = conn.execute(
                """
                SELECT id FROM agent_run_events
                WHERE run_id = ?
                ORDER BY id DESC
                LIMIT 1 OFFSET ?
                """,
                (run_id, safe_max - 1),
            ).fetchone()
            if keep_from_id_row is None:
                return 0
            threshold_id = int(keep_from_id_row["id"])
            deleted = conn.execute(
                "DELETE FROM agent_run_events WHERE run_id = ? AND id < ?",
                (run_id, threshold_id),
            ).rowcount
            conn.commit()
            return int(deleted or 0)

    def count_runs(self) -> int:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM agent_runs").fetchone()
        return int(row["c"] if row else 0)

    def count_runs_by_state(self) -> dict[str, int]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT state, COUNT(*) AS c FROM agent_runs GROUP BY state"
            ).fetchall()
        return {str(row["state"]): int(row["c"]) for row in rows}

    def cleanup_old_runs(
        self,
        cutoff_iso: str,
        terminal_states: set[AgentRunState],
        dry_run: bool = False,
    ) -> tuple[int, int]:
        states = sorted(state.value for state in terminal_states)
        if not states:
            return (0, 0)
        placeholders = ",".join("?" for _ in states)
        params = [cutoff_iso, *states]
        with self._lock, self._connect() as conn:
            run_rows = conn.execute(
                f"""
                SELECT run_id FROM agent_runs
                WHERE updated_at < ?
                  AND state IN ({placeholders})
                """,
                params,
            ).fetchall()
            run_ids = [str(row["run_id"]) for row in run_rows]
            if not run_ids:
                return (0, 0)

            run_placeholders = ",".join("?" for _ in run_ids)
            events_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM agent_run_events WHERE run_id IN ({run_placeholders})",
                run_ids,
            ).fetchone()
            deleted_events = int(events_row["c"] if events_row else 0)
            deleted_runs = len(run_ids)

            if dry_run:
                return deleted_runs, deleted_events

            conn.execute(
                f"DELETE FROM agent_run_events WHERE run_id IN ({run_placeholders})",
                run_ids,
            )
            conn.execute(
                f"DELETE FROM agent_runs WHERE run_id IN ({run_placeholders})",
                run_ids,
            )
            conn.commit()
            return deleted_runs, deleted_events

    def _row_to_run(self, row: sqlite3.Row) -> AgentRunRecordResponse:
        attempted = [item for item in str(row["attempted_models"] or "").split("\n") if item]
        return AgentRunRecordResponse(
            run_id=row["run_id"],
            agent_id=row["agent_id"],
            agent_name=row["agent_name"],
            state=AgentRunState(row["state"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            input=row["input"],
            session_id=row["session_id"],
            provider=row["provider"],
            model=row["model"],
            attempts=int(row["attempts"] or 0),
            max_attempts=int(row["max_attempts"] or 1),
            failure_class=row["failure_class"],
            attempted_models=attempted,
            response=row["response"] or "",
            error=row["error"],
        )

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {row[1] for row in rows}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
