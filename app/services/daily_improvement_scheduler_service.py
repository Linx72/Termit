"""Built-in daily scheduler for autonomous project improvement."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Callable, Optional

from app.core.config import Settings
from app.services.daily_improvement_service import DailyImprovementService


class DailyImprovementSchedulerService:
    def __init__(
        self,
        *,
        settings: Settings,
        improvement_service: DailyImprovementService,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._settings = settings
        self._improvement_service = improvement_service
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._state_path = Path(settings.daily_improvement_state_path)
        self._lock = Lock()
        self._stop = Event()
        self._thread: Optional[Thread] = None
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        if not self._settings.daily_improvement_enabled:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(
            target=self._loop,
            name="daily-improvement-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def status(self) -> dict[str, object]:
        last_run = self._read_state()
        return {
            "enabled": self._settings.daily_improvement_enabled,
            "hour_utc": self._settings.daily_improvement_hour,
            "minute_utc": self._settings.daily_improvement_minute,
            "agent_id": self._settings.daily_improvement_agent_id,
            "max_agent_runs": self._settings.daily_improvement_max_agent_runs,
            "max_dlq_replay": self._settings.daily_improvement_max_dlq_replay,
            "max_eval_fixes": self._settings.daily_improvement_max_eval_fixes,
            "eval_probe_limit": self._settings.daily_improvement_eval_probe_limit,
            "run_eval_probe": self._settings.daily_improvement_run_eval_probe,
            "auto_create_agent": self._settings.daily_improvement_auto_create_agent,
            "last_run_slot": last_run.get("slot"),
            "last_run_at": last_run.get("run_at"),
            "last_run_source": last_run.get("source"),
            "last_status": last_run.get("status"),
            "last_action_count": last_run.get("action_count"),
            "thread_alive": self._thread is not None and self._thread.is_alive(),
        }

    def preview_plan(self) -> dict[str, object]:
        return self._improvement_service.build_plan()

    def trigger_now(self) -> dict[str, object]:
        return self._run_once(source="manual")

    def should_run_for_time(self, moment: datetime) -> bool:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        else:
            moment = moment.astimezone(timezone.utc)
        if moment.hour != self._settings.daily_improvement_hour:
            return False
        if moment.minute != self._settings.daily_improvement_minute:
            return False
        slot = self._slot_key(moment)
        last_run = self._read_state()
        return last_run.get("slot") != slot

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                now = self._now_provider()
                if self.should_run_for_time(now):
                    self._run_once(source="builtin_scheduler")
            except Exception:  # noqa: BLE001
                pass
            self._stop.wait(30)

    def _run_once(self, *, source: str) -> dict[str, object]:
        with self._lock:
            now = self._now_provider()
            slot = self._slot_key(now)
            last_run = self._read_state()
            if last_run.get("slot") == slot and source == "builtin_scheduler":
                return {
                    "status": "skipped",
                    "detail": "Already ran for this daily slot.",
                    "slot": slot,
                }

            plan = self._improvement_service.build_plan()
            if not plan.get("actions"):
                result = {
                    "status": "skipped",
                    "source": source,
                    "detail": "No improvement actions planned.",
                    "plan": plan,
                    "results": [],
                }
            else:
                result = self._improvement_service.execute_plan(plan, source=source)

            self._write_state(
                {
                    "slot": slot,
                    "run_at": now.isoformat(),
                    "source": source,
                    "status": result.get("status"),
                    "action_count": plan.get("action_count", 0),
                }
            )
            result["slot"] = slot
            return result

    @staticmethod
    def _slot_key(moment: datetime) -> str:
        utc = moment.astimezone(timezone.utc)
        return utc.strftime("%Y-%m-%d")

    def _read_state(self) -> dict[str, object]:
        if not self._state_path.exists():
            return {}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_state(self, payload: dict[str, object]) -> None:
        self._state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
