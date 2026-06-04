"""SQLite store for async media render jobs (I2V, T2V)."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MediaJobRecord:
    job_id: str
    job_type: str
    status: str
    provider: str
    payload_json: str
    result_asset_id: Optional[str]
    error: Optional[str]
    cost_usd: float
    run_id: Optional[str]
    project_id: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status,
            "provider": self.provider,
            "payload": json.loads(self.payload_json) if self.payload_json else {},
            "result_asset_id": self.result_asset_id,
            "error": self.error,
            "cost_usd": self.cost_usd,
            "run_id": self.run_id,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class MediaJobStore:
    def __init__(self, db_path: str) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS media_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    result_asset_id TEXT,
                    error TEXT,
                    cost_usd REAL NOT NULL DEFAULT 0,
                    run_id TEXT,
                    project_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def create(
        self,
        *,
        job_type: str,
        provider: str,
        payload: dict[str, object],
        project_id: str = "default",
        run_id: Optional[str] = None,
        cost_usd: float = 0.0,
    ) -> MediaJobRecord:
        job_id = f"mjob_{uuid4().hex[:12]}"
        now = _utc_now()
        record = MediaJobRecord(
            job_id=job_id,
            job_type=job_type,
            status="pending",
            provider=provider,
            payload_json=json.dumps(payload, ensure_ascii=False),
            result_asset_id=None,
            error=None,
            cost_usd=cost_usd,
            run_id=run_id,
            project_id=project_id,
            created_at=now,
            updated_at=now,
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO media_jobs (
                    job_id, job_type, status, provider, payload_json,
                    result_asset_id, error, cost_usd, run_id, project_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.job_type,
                    record.status,
                    record.provider,
                    record.payload_json,
                    record.cost_usd,
                    record.run_id,
                    record.project_id,
                    record.created_at,
                    record.updated_at,
                ),
            )
            conn.commit()
        return record

    def get(self, job_id: str) -> Optional[MediaJobRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM media_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def update(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        result_asset_id: Optional[str] = None,
        error: Optional[str] = None,
        cost_usd: Optional[float] = None,
    ) -> Optional[MediaJobRecord]:
        record = self.get(job_id)
        if record is None:
            return None
        if status is not None:
            record.status = status
        if result_asset_id is not None:
            record.result_asset_id = result_asset_id
        if error is not None:
            record.error = error
        if cost_usd is not None:
            record.cost_usd = cost_usd
        record.updated_at = _utc_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE media_jobs SET
                    status = ?, result_asset_id = ?, error = ?,
                    cost_usd = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    record.status,
                    record.result_asset_id,
                    record.error,
                    record.cost_usd,
                    record.updated_at,
                    job_id,
                ),
            )
            conn.commit()
        return record

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> MediaJobRecord:
        return MediaJobRecord(
            job_id=str(row["job_id"]),
            job_type=str(row["job_type"]),
            status=str(row["status"]),
            provider=str(row["provider"]),
            payload_json=str(row["payload_json"]),
            result_asset_id=row["result_asset_id"],
            error=row["error"],
            cost_usd=float(row["cost_usd"]),
            run_id=row["run_id"],
            project_id=str(row["project_id"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
