import tempfile
import unittest
from pathlib import Path

from app.services.agent_maintenance_scheduler_service import AgentMaintenanceSchedulerService
from app.services.metrics_snapshot_store import MetricsSnapshotStore
from app.services.telemetry_store import TelemetryStore


class _StubAgentService:
    def __init__(self) -> None:
        self.calls = 0

    def cleanup_runs(self, retention_days=None, dry_run=False):  # type: ignore[no-untyped-def]
        self.calls += 1
        return {
            "dry_run": dry_run,
            "retention_days": retention_days or 14,
            "cutoff_timestamp": "2026-01-01T00:00:00+00:00",
            "deleted_runs": 1 if not dry_run else 0,
            "deleted_events": 2 if not dry_run else 0,
            "remaining_runs": 10,
        }


class AgentMaintenanceSchedulerServiceTests(unittest.TestCase):
    def test_manual_cleanup_and_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            telemetry = TelemetryStore()
            snapshots = MetricsSnapshotStore(str(Path(tmp) / "metrics.jsonl"))
            scheduler = AgentMaintenanceSchedulerService(
                agent_service=_StubAgentService(),  # type: ignore[arg-type]
                telemetry_store=telemetry,
                metrics_snapshot_store=snapshots,
                enabled=False,
                cleanup_interval_seconds=60,
                metrics_snapshot_interval_seconds=60,
            )
            cleanup = scheduler.run_cleanup_once(dry_run=True)
            self.assertTrue(cleanup["dry_run"])
            snapshot = scheduler.run_metrics_snapshot_once()
            self.assertIn("captured_at", snapshot)
            status = scheduler.status()
            self.assertFalse(status["thread_alive"])
            self.assertIsNotNone(status["last_metrics_snapshot_at"])


if __name__ == "__main__":
    unittest.main()
