from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Iterator, Optional
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
        with closing(self._connect()) as conn:
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
        with self._lock, closing(self._connect()) as conn:
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
        with closing(self._connect()) as conn:
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

    def export_otel_json(self, run_id: str, *, limit: int = 100) -> list[dict[str, object]]:
        """Export run spans in OTLP/OTEL-friendly JSON (for collectors and debug)."""
        rows = list(reversed(self.list_for_run(run_id, limit=limit)))
        trace_id = run_id.replace("-", "").replace("_", "")[:32].ljust(32, "0")
        payload: list[dict[str, object]] = []
        for row in rows:
            created = datetime.fromisoformat(str(row["created_at"]))
            start_ns = int(created.timestamp() * 1_000_000_000)
            duration_ms = int(row.get("duration_ms") or 0)
            end_ns = start_ns + duration_ms * 1_000_000
            span_id = str(row["span_id"]).replace("span_", "")[:16].ljust(16, "0")
            status = str(row.get("status") or "ok")
            payload.append(
                {
                    "traceId": trace_id,
                    "spanId": span_id,
                    "name": str(row.get("name") or "span"),
                    "kind": "SPAN_KIND_INTERNAL",
                    "startTimeUnixNano": str(start_ns),
                    "endTimeUnixNano": str(end_ns),
                    "status": {
                        "code": "STATUS_CODE_OK" if status == "ok" else "STATUS_CODE_ERROR",
                    },
                    "attributes": [
                        {"key": "termit.status", "value": {"stringValue": status}},
                        {"key": "termit.detail", "value": {"stringValue": str(row.get("detail") or "")[:500]}},
                        {"key": "termit.run_id", "value": {"stringValue": run_id}},
                    ],
                }
            )
        return payload
