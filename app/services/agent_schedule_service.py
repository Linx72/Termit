from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Callable, Optional
from uuid import uuid4

from app.domain.schemas import AgentRunRequest, AgentRunState


class AgentScheduleService:
    def __init__(
        self,
        db_path: str,
        enqueue_fn: Callable[[str, AgentRunRequest], str],
        poll_interval_seconds: int = 60,
    ) -> None:
        self.db_path = str(Path(db_path).resolve())
        self._enqueue_fn = enqueue_fn
        self._poll_interval_seconds = max(15, poll_interval_seconds)
        self._lock = Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._enabled = True
        self._init_db()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if enabled:
            self.start()
        else:
            self.stop()

    def status(self) -> dict[str, object]:
        return {
            "enabled": self._enabled,
            "thread_alive": self._thread is not None and self._thread.is_alive(),
            "poll_interval_seconds": self._poll_interval_seconds,
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_schedules (
                    schedule_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    cron TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    last_run_at TEXT,
                    next_run_at TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def start(self) -> None:
        if not self._enabled:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="agent-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def create_schedule(
        self,
        *,
        agent_id: str,
        cron: str,
        payload: AgentRunRequest,
    ) -> dict[str, object]:
        schedule_id = f"sched_{uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        next_run = self._compute_next_run(cron)
        with self._lock, closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO agent_schedules(
                    schedule_id, agent_id, cron, payload_json, enabled, last_run_at, next_run_at, created_at
                ) VALUES (?, ?, ?, ?, 1, NULL, ?, ?)
                """,
                (
                    schedule_id,
                    agent_id,
                    cron.strip(),
                    payload.model_dump_json(),
                    next_run,
                    now,
                ),
            )
            conn.commit()
        return {
            "schedule_id": schedule_id,
            "agent_id": agent_id,
            "cron": cron,
            "enabled": True,
            "next_run_at": next_run,
        }

    def list_schedules(self, agent_id: str | None = None) -> list[dict[str, object]]:
        with closing(self._connect()) as conn:
            if agent_id:
                rows = conn.execute(
                    "SELECT * FROM agent_schedules WHERE agent_id = ? ORDER BY created_at DESC",
                    (agent_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agent_schedules ORDER BY created_at DESC"
                ).fetchall()
        return [dict(row) for row in rows]

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self._stop.wait(self._poll_interval_seconds)

    def _tick(self) -> None:
        now = datetime.now(timezone.utc)
        due: list[tuple[str, str, str, str]] = []
        with self._lock, closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT schedule_id, agent_id, cron, payload_json, next_run_at FROM agent_schedules WHERE enabled = 1"
            ).fetchall()
            for row in rows:
                next_run_at = row["next_run_at"]
                if not next_run_at:
                    continue
                try:
                    next_dt = datetime.fromisoformat(next_run_at)
                except ValueError:
                    continue
                if next_dt <= now:
                    due.append(
                        (row["schedule_id"], row["agent_id"], row["cron"], row["payload_json"])
                    )
        for schedule_id, agent_id, cron, payload_json in due:
            payload = AgentRunRequest.model_validate_json(payload_json)
            run_id = self._enqueue_fn(agent_id, payload)
            next_run = self._compute_next_run(cron)
            fired_at = datetime.now(timezone.utc).isoformat()
            with self._lock, closing(self._connect()) as conn:
                conn.execute(
                    """
                    UPDATE agent_schedules
                    SET last_run_at = ?, next_run_at = ?
                    WHERE schedule_id = ?
                    """,
                    (fired_at, next_run, schedule_id),
                )
                conn.commit()
            _ = run_id

    @staticmethod
    def _compute_next_run(cron: str) -> str:
        """Minimal cron support: @hourly, @daily, or interval minutes like '*/5'."""
        now = datetime.now(timezone.utc)
        token = cron.strip().lower()
        if token in {"@hourly", "hourly"}:
            delta_minutes = 60
        elif token in {"@daily", "daily"}:
            delta_minutes = 24 * 60
        elif token.startswith("*/"):
            try:
                delta_minutes = max(1, int(token[2:]))
            except ValueError:
                delta_minutes = 60
        else:
            delta_minutes = 60
        next_dt = datetime.fromtimestamp(now.timestamp() + delta_minutes * 60, tz=timezone.utc)
        return next_dt.isoformat()
