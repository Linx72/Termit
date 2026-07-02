from __future__ import annotations

from datetime import datetime, timezone
from threading import Event, Lock, Thread
from typing import Optional

from app.services.agent_service import AgentService
from app.services.metrics_snapshot_store import MetricsSnapshotStore
from app.services.telemetry_store import TelemetryStore


class AgentMaintenanceSchedulerService:
    def __init__(
        self,
        *,
        agent_service: AgentService,
        telemetry_store: TelemetryStore,
        metrics_snapshot_store: MetricsSnapshotStore,
        enabled: bool = True,
        cleanup_interval_seconds: int = 3600,
        metrics_snapshot_interval_seconds: int = 900,
        stale_run_timeout_seconds: int = 7200,
    ) -> None:
        self._agent_service = agent_service
        self._telemetry_store = telemetry_store
        self._metrics_snapshot_store = metrics_snapshot_store
        self._enabled = enabled
        self._cleanup_interval_seconds = max(30, cleanup_interval_seconds)
        self._metrics_snapshot_interval_seconds = max(30, metrics_snapshot_interval_seconds)
        self._stale_run_timeout_seconds = max(60, stale_run_timeout_seconds)
        self._stop = Event()
        self._lock = Lock()
        self._thread: Optional[Thread] = None
        self._last_cleanup_at: Optional[str] = None
        self._last_metrics_snapshot_at: Optional[str] = None
        self._cleanup_runs_deleted_total = 0
        self._cleanup_events_deleted_total = 0
        self._cleanup_errors_total = 0
        self._snapshot_errors_total = 0
        self._stale_cancelled_total = 0
        self._loop_crash_count = 0

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if enabled:
            self.start()
        else:
            self.stop()

    def start(self) -> None:
        if not self._enabled:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._loop, name="agent-maintenance-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "enabled": self._enabled,
                "thread_alive": self._thread is not None and self._thread.is_alive(),
                "cleanup_interval_seconds": self._cleanup_interval_seconds,
                "metrics_snapshot_interval_seconds": self._metrics_snapshot_interval_seconds,
                "stale_run_timeout_seconds": self._stale_run_timeout_seconds,
                "last_cleanup_at": self._last_cleanup_at,
                "last_metrics_snapshot_at": self._last_metrics_snapshot_at,
                "cleanup_runs_deleted_total": self._cleanup_runs_deleted_total,
                "cleanup_events_deleted_total": self._cleanup_events_deleted_total,
                "stale_cancelled_total": self._stale_cancelled_total,
                "cleanup_errors_total": self._cleanup_errors_total,
                "snapshot_errors_total": self._snapshot_errors_total,
                "loop_crash_count": self._loop_crash_count,
            }

    def run_cleanup_once(self, *, dry_run: bool = False) -> dict[str, object]:
        stale_before = datetime.now(timezone.utc).timestamp() - float(self._stale_run_timeout_seconds)
        stale_before_iso = datetime.fromtimestamp(stale_before, timezone.utc).isoformat()
        stale_result = self._agent_service.cleanup_stale_active_runs(
            stale_before_iso=stale_before_iso,
            dry_run=dry_run,
        )
        result = self._agent_service.cleanup_runs(dry_run=dry_run)
        result["stale_before"] = stale_before_iso
        result["cancelled_stale_runs"] = int(stale_result.get("cancelled_runs", 0))
        if not dry_run:
            with self._lock:
                self._last_cleanup_at = datetime.now(timezone.utc).isoformat()
                self._cleanup_runs_deleted_total += int(result.get("deleted_runs", 0))
                self._cleanup_events_deleted_total += int(result.get("deleted_events", 0))
                self._stale_cancelled_total += int(result.get("cancelled_stale_runs", 0))
        return result

    def run_metrics_snapshot_once(self) -> dict[str, object]:
        snapshot = self._metrics_snapshot_store.append_snapshot(self._telemetry_store.snapshot())
        with self._lock:
            self._last_metrics_snapshot_at = datetime.now(timezone.utc).isoformat()
        return snapshot.model_dump(mode="json")

    def _loop(self) -> None:
        try:
            self._run_loop()
        except Exception:  # noqa: BLE001 — поток не должен умирать при любом исключении
            import logging
            _logger = logging.getLogger("termit.maintenance")
            _logger.exception("Maintenance loop crashed — поток будет пересоздан health-check'ом")
            with self._lock:
                self._loop_crash_count += 1

    def _run_loop(self) -> None:
        next_cleanup = 0.0
        next_snapshot = 0.0
        while not self._stop.is_set():
            now = self._monotonic()
            if now >= next_cleanup:
                try:
                    self.run_cleanup_once(dry_run=False)
                except Exception:  # noqa: BLE001
                    with self._lock:
                        self._cleanup_errors_total += 1
                next_cleanup = now + self._cleanup_interval_seconds
            if now >= next_snapshot:
                try:
                    self.run_metrics_snapshot_once()
                except Exception:  # noqa: BLE001
                    with self._lock:
                        self._snapshot_errors_total += 1
                next_snapshot = now + self._metrics_snapshot_interval_seconds
            self._stop.wait(1.0)

    @staticmethod
    def _monotonic() -> float:
        import time

        return time.monotonic()
