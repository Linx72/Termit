"""Tests for Stage1 stuck pipeline recovery and signal export."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.finetune_service import FinetunePipelineRunRecord, FinetuneService


class FinetuneStuckRecoveryTests(unittest.TestCase):
    def _build_service(self, root: Path) -> FinetuneService:
        signals = root / "training_signals.jsonl"
        signals.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "instruction": f"task {idx}",
                            "input": "",
                            "output": f"completed output {idx}" * 3,
                            "source": "training_signal",
                            "category": "agent",
                        }
                    )
                    for idx in range(12)
                ]
            ),
            encoding="utf-8",
        )
        pipelines = root / "pipelines.json"
        stale = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        pipelines.write_text(
            json.dumps(
                {
                    "runs": [
                        {
                            "run_id": "ftpbg_stuck",
                            "status": "running",
                            "created_at": stale,
                            "updated_at": stale,
                            "cancelled": False,
                            "request": {"name": "weekly-stage1", "base_model": "ollama:deepseek-coder"},
                            "result": None,
                            "error": None,
                            "stages": [
                                {"stage": "execute", "status": "running", "detail": "started"}
                            ],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return FinetuneService(
            datasets_dir=str(root / "datasets"),
            jobs_path=str(root / "jobs.json"),
            adapters_path=str(root / "adapters.json"),
            pipelines_path=str(pipelines),
            feedback_file_path=str(root / "feedback.jsonl"),
            task_sqlite_path=str(root / "tasks.db"),
            agent_run_sqlite_path=str(root / "agent_runs.db"),
            training_signals_path=str(signals),
            pipeline_stuck_timeout_seconds=60,
        )

    def test_recovers_stuck_running_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(Path(tmp))
            recovered = service.recover_stuck_pipeline_runs(stale_seconds=60)
            self.assertEqual(len(recovered), 1)
            self.assertEqual(recovered[0]["new_status"], "failed")
            run = service.get_stage1_pipeline_run("ftpbg_stuck")
            assert run is not None
            self.assertEqual(run["status"], "failed")

    def test_export_training_signals_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(Path(tmp))
            export = service.export_training_signals_dataset(min_samples=5, limit=50)
            self.assertGreaterEqual(int(export["sample_count"]), 5)
            self.assertTrue(Path(str(export["dataset_path"])).exists())


if __name__ == "__main__":
    unittest.main()
