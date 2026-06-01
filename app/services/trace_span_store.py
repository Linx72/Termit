from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional
from uuid import uuid4


class TraceSpanStore:
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trace_spans (
                    span_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_trace_spans_run ON trace_spans(run_id, created_at)"
            )
            conn.commit()

    def record(
        self,
        *,
        run_id: str,
        name: str,
        status: str = "ok",
        detail: str = "",
        duration_ms: int = 0,
    ) -> str:
        span_id = f"span_{uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO trace_spans(span_id, run_id, name, status, detail, duration_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (span_id, run_id, name, status, detail[:2000], max(0, duration_ms), created_at),
            )
            conn.commit()
        return span_id

    def list_for_run(self, run_id: str, limit: int = 100) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT span_id, run_id, name, status, detail, duration_ms, created_at
                FROM trace_spans
                WHERE run_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (run_id, max(1, limit)),
            ).fetchall()
        return [dict(row) for row in rows]

    def export_json(self, run_id: str) -> str:
        return json.dumps(self.list_for_run(run_id), ensure_ascii=True)
