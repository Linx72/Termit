"""Desktop workflow events for North Star KPI measurement."""

from __future__ import annotations

import json
import statistics
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DesktopWorkflowTelemetryService:
    def __init__(self, state_dir: str) -> None:
        self._dir = Path(state_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "workflow_events.jsonl"
        self._lock = threading.Lock()

    def record(
        self,
        *,
        event_type: str,
        journey_id: str = "",
        execution_mode: str = "",
        duration_ms: Optional[int] = None,
        ok: Optional[bool] = None,
        detail: str = "",
        metadata: Optional[dict[str, object]] = None,
    ) -> dict[str, object]:
        row = {
            "event_id": f"wfe_{uuid4().hex[:10]}",
            "event_type": event_type.strip()[:64],
            "journey_id": journey_id.strip()[:64],
            "execution_mode": execution_mode.strip()[:16],
            "duration_ms": duration_ms,
            "ok": ok,
            "detail": detail.strip()[:500],
            "metadata": metadata or {},
            "timestamp": _utc_now(),
        }
        with self._lock:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=True) + "\n")
        return row

    def _read_events(self, *, limit: int = 5000) -> list[dict[str, object]]:
        if not self._path.is_file():
            return []
        rows: list[dict[str, object]] = []
        with self._lock:
            for line in self._path.read_text(encoding="utf-8").splitlines():
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

    def summarize(self, patch_outcomes_path: str) -> dict[str, object]:
        events = self._read_events()
        ttfuc_samples: list[float] = []
        resume_samples: list[float] = []
        verify_ok = 0
        verify_fail = 0
        local_runs = 0
        total_runs = 0

        sessions: dict[str, dict[str, object]] = {}
        for event in events:
            event_type = str(event.get("event_type", ""))
            if event_type == "journey_started":
                sid = str(event.get("event_id", ""))
                sessions[sid] = {"started_at": event.get("timestamp"), "journey_id": event.get("journey_id")}
            elif event_type == "composer_applied" and event.get("duration_ms") is not None:
                ttfuc_samples.append(float(event["duration_ms"]) / 1000.0)
            elif event_type == "verify_completed":
                if event.get("ok") is True:
                    verify_ok += 1
                elif event.get("ok") is False:
                    verify_fail += 1
            elif event_type == "agent_run_created":
                total_runs += 1
                if str(event.get("execution_mode", "")).lower() == "local":
                    local_runs += 1
            elif event_type == "agent_resume" and event.get("duration_ms") is not None:
                resume_samples.append(float(event["duration_ms"]) / 1000.0)

        patch_acceptance = self._patch_acceptance_rate(patch_outcomes_path)

        verify_total = verify_ok + verify_fail
        verify_pass_rate = verify_ok / verify_total if verify_total else 0.0
        local_share = local_runs / total_runs if total_runs else 0.0
        ttfuc_median = statistics.median(ttfuc_samples) if ttfuc_samples else None
        resume_median = statistics.median(resume_samples) if resume_samples else None

        return {
            "event_count": len(events),
            "ttfuc_median_seconds": ttfuc_median,
            "patch_acceptance_rate": patch_acceptance,
            "verify_pass_rate": verify_pass_rate,
            "verify_ok": verify_ok,
            "verify_fail": verify_fail,
            "agent_resume_median_seconds": resume_median,
            "local_only_task_share": local_share,
            "agent_runs_local": local_runs,
            "agent_runs_total": total_runs,
        }

    @staticmethod
    def _patch_acceptance_rate(patch_outcomes_path: str) -> float:
        path = Path(patch_outcomes_path)
        if not path.is_file():
            return 0.0
        applied = 0
        reverted = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            event = str(item.get("event", ""))
            if event == "applied":
                applied += 1
            elif event == "reverted":
                reverted += 1
        if applied == 0:
            return 0.0
        kept = max(0, applied - reverted)
        return kept / applied
