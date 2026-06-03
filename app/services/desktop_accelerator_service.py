"""Shared runs and remote heavy jobs for desktop online accelerator."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DesktopAcceleratorService:
    """Persists shared agent runs and background heavy jobs for desktop clients."""

    def __init__(
        self,
        state_dir: str,
        *,
        run_lookup: Callable[[str], dict[str, object] | None] | None = None,
        eval_suite_runner: Callable[[str | None, int | None], dict[str, object]] | None = None,
    ) -> None:
        self._dir = Path(state_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._shared_path = self._dir / "shared_runs.jsonl"
        self._jobs_path = self._dir / "heavy_jobs.jsonl"
        self._lock = threading.Lock()
        self._run_lookup = run_lookup
        self._eval_suite_runner = eval_suite_runner

    def list_shared_runs(self, limit: int = 30, team: str | None = None) -> list[dict[str, object]]:
        rows = self._read_jsonl(self._shared_path, limit=500)
        if team:
            rows = [row for row in rows if str(row.get("team", "")) == team]
        rows.sort(key=lambda item: str(item.get("shared_at", "")), reverse=True)
        return rows[: max(1, min(limit, 100))]

    def share_run(
        self,
        *,
        run_id: str,
        team: str = "default",
        note: str = "",
        shared_by: str = "desktop",
    ) -> dict[str, object]:
        snapshot: dict[str, object] = {"run_id": run_id}
        if self._run_lookup is not None:
            looked_up = self._run_lookup(run_id)
            if looked_up is not None:
                snapshot = looked_up
        record = {
            "share_id": f"share_{uuid4().hex[:10]}",
            "run_id": run_id,
            "team": team.strip() or "default",
            "note": note.strip()[:500],
            "shared_by": shared_by.strip()[:64] or "desktop",
            "shared_at": _utc_now(),
            "snapshot": snapshot,
        }
        self._append_jsonl(self._shared_path, record)
        return record

    def list_heavy_jobs(self, limit: int = 20) -> list[dict[str, object]]:
        rows = self._read_jsonl(self._jobs_path, limit=500)
        rows.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return rows[: max(1, min(limit, 50))]

    def enqueue_heavy_job(
        self,
        *,
        job_type: str,
        payload: dict[str, object] | None = None,
        requested_by: str = "desktop",
    ) -> dict[str, object]:
        safe_type = job_type.strip().lower()
        if safe_type not in {"eval_suite", "orchestration", "refactor_batch"}:
            raise ValueError(f"Unsupported heavy job type: {job_type}")

        job_id = f"hjob_{uuid4().hex[:12]}"
        record: dict[str, object] = {
            "job_id": job_id,
            "job_type": safe_type,
            "state": "queued",
            "payload": payload or {},
            "requested_by": requested_by.strip()[:64] or "desktop",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "result": None,
            "error": None,
        }
        self._append_jsonl(self._jobs_path, record)
        thread = threading.Thread(
            target=self._execute_heavy_job,
            args=(job_id, safe_type, payload or {}),
            daemon=True,
        )
        thread.start()
        return record

    def get_heavy_job(self, job_id: str) -> Optional[dict[str, object]]:
        for row in self._read_jsonl(self._jobs_path, limit=1000):
            if str(row.get("job_id")) == job_id:
                return row
        return None

    def _execute_heavy_job(self, job_id: str, job_type: str, payload: dict[str, object]) -> None:
        self._update_job(job_id, state="running")
        try:
            if job_type == "eval_suite" and self._eval_suite_runner is not None:
                category = str(payload.get("category", "")).strip() or None
                limit_raw = payload.get("limit")
                limit = int(limit_raw) if limit_raw is not None else None
                result = self._eval_suite_runner(category, limit)
                self._update_job(job_id, state="completed", result=result)
                return
            if job_type == "orchestration":
                self._update_job(
                    job_id,
                    state="completed",
                    result={
                        "message": "Orchestration job accepted; use /api/orchestration/run for full execution.",
                        "payload": payload,
                    },
                )
                return
            if job_type == "refactor_batch":
                self._update_job(
                    job_id,
                    state="completed",
                    result={
                        "message": "Refactor batch queued for desktop composer workflow.",
                        "payload": payload,
                    },
                )
                return
            self._update_job(job_id, state="failed", error=f"No runner configured for {job_type}")
        except Exception as exc:  # noqa: BLE001 — background worker must not crash
            self._update_job(job_id, state="failed", error=str(exc))

    def _update_job(
        self,
        job_id: str,
        *,
        state: str,
        result: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            rows = self._read_jsonl(self._jobs_path, limit=2000)
            updated: list[dict[str, object]] = []
            found = False
            for row in rows:
                if str(row.get("job_id")) != job_id:
                    updated.append(row)
                    continue
                found = True
                next_row = dict(row)
                next_row["state"] = state
                next_row["updated_at"] = _utc_now()
                if result is not None:
                    next_row["result"] = result
                if error is not None:
                    next_row["error"] = error
                updated.append(next_row)
            if found:
                self._write_jsonl(self._jobs_path, updated)

    def _read_jsonl(self, path: Path, *, limit: int) -> list[dict[str, object]]:
        if not path.is_file():
            return []
        rows: list[dict[str, object]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(rows) >= limit:
                break
        return rows

    def _append_jsonl(self, path: Path, record: dict[str, object]) -> None:
        with self._lock:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    def _write_jsonl(self, path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=True) + "\n")
