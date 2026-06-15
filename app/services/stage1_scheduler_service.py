from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Callable, Optional

from app.core.config import Settings
from app.domain.schemas import FinetuneStage1RunRequest
from app.services.eval_service import EvalService
from app.services.finetune_service import FinetuneService


class Stage1SchedulerService:
    def __init__(
        self,
        *,
        settings: Settings,
        finetune_service: FinetuneService,
        eval_service: EvalService,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._settings = settings
        self._finetune_service = finetune_service
        self._eval_service = eval_service
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._state_path = Path(settings.stage1_schedule_state_path)
        self._lock = Lock()
        self._stop = Event()
        self._thread: Optional[Thread] = None
        self._runtime_enabled: Optional[bool] = None
        self._state_path.parent.mkdir(parents=True, exist_ok=True)

    def _is_enabled(self) -> bool:
        if self._runtime_enabled is not None:
            return self._runtime_enabled
        return self._settings.stage1_schedule_enabled

    def set_enabled(self, enabled: bool) -> None:
        self._runtime_enabled = enabled
        if enabled:
            self.start()
        else:
            self.stop()

    def start(self) -> None:
        if not self._is_enabled():
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._loop, name="stage1-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def trigger_now(self) -> dict[str, object]:
        return self._enqueue_once(source="manual")

    def status(self) -> dict[str, object]:
        last_run = self._read_state()
        return {
            "enabled": self._is_enabled(),
            "weekday": self._settings.stage1_schedule_weekday,
            "hour_utc": self._settings.stage1_schedule_hour,
            "minute_utc": self._settings.stage1_schedule_minute,
            "name": self._settings.stage1_schedule_name,
            "base_model": self._resolve_base_model(),
            "min_samples": self._settings.stage1_schedule_min_samples,
            "run_eval_baseline": self._settings.stage1_schedule_run_eval_baseline,
            "eval_limit": self._settings.stage1_schedule_eval_limit,
            "auto_register_adapter": self._settings.stage1_schedule_auto_register_adapter,
            "last_run_slot": last_run.get("slot"),
            "last_run_id": last_run.get("run_id"),
            "last_run_at": last_run.get("run_at"),
            "last_run_source": last_run.get("source"),
            "thread_alive": self._thread is not None and self._thread.is_alive(),
        }

    def should_run_for_time(self, moment: datetime) -> bool:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        else:
            moment = moment.astimezone(timezone.utc)
        if moment.weekday() != self._settings.stage1_schedule_weekday:
            return False
        if moment.hour != self._settings.stage1_schedule_hour:
            return False
        if moment.minute != self._settings.stage1_schedule_minute:
            return False
        slot = self._slot_key(moment)
        last_run = self._read_state()
        return last_run.get("slot") != slot

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                now = self._now_provider()
                if self.should_run_for_time(now):
                    self._enqueue_once(source="builtin_scheduler")
            except Exception:  # noqa: BLE001
                pass
            self._stop.wait(30)

    def _enqueue_once(self, *, source: str) -> dict[str, object]:
        self._finetune_service.recover_stuck_pipeline_runs(requeue=False)
        with self._lock:
            now = self._now_provider()
            slot = self._slot_key(now)
            last_run = self._read_state()
            if last_run.get("slot") == slot and source == "builtin_scheduler":
                existing_run_id = last_run.get("run_id")
                if isinstance(existing_run_id, str):
                    existing = self._finetune_service.get_stage1_pipeline_run(existing_run_id)
                    if existing is not None:
                        return existing

            signal_count = len(
                self._finetune_service.training_signal_store.load_samples(5000)
            )
            min_signals = max(
                self._settings.stage1_schedule_min_samples,
                self._settings.finetune_min_signals_for_train,
            )
            if source == "builtin_scheduler" and signal_count < min_signals:
                return {
                    "status": "skipped",
                    "detail": f"Need at least {min_signals} training signals (have {signal_count}).",
                }

            payload = FinetuneStage1RunRequest(
                name=self._settings.stage1_schedule_name,
                base_model=self._resolve_base_model(),
                min_samples=self._settings.stage1_schedule_min_samples,
                run_eval_baseline=self._settings.stage1_schedule_run_eval_baseline,
                eval_limit=self._settings.stage1_schedule_eval_limit,
                auto_register_adapter=self._settings.stage1_schedule_auto_register_adapter,
            )

            def baseline_runner(request_payload: FinetuneStage1RunRequest) -> dict[str, object]:
                return self._eval_service.run_suite(
                    category=request_payload.eval_category,
                    limit=request_payload.eval_limit,
                    persist_report=True,
                )

            queued = self._finetune_service.enqueue_stage1_pipeline(payload)
            self._finetune_service.drain_stage1_pipeline_queue(baseline_runner, wait=False)
            self._write_state(
                {
                    "slot": slot,
                    "run_id": queued["run_id"],
                    "run_at": now.isoformat(),
                    "source": source,
                }
            )
            return queued

    def _resolve_base_model(self) -> str:
        from app.core.model_roles import resolve_stage1_base_model

        return resolve_stage1_base_model(self._settings, "")

    @staticmethod
    def _slot_key(moment: datetime) -> str:
        utc = moment.astimezone(timezone.utc)
        return utc.strftime("%Y-%m-%dT%H:%M")

    def _read_state(self) -> dict[str, object]:
        if not self._state_path.exists():
            return {}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_state(self, payload: dict[str, object]) -> None:
        self._state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
