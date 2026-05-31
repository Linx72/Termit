import json
import tempfile
import time
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.config import get_settings
from app.services.finetune_service import FinetuneService
from app.services.stage1_scheduler_service import Stage1SchedulerService
from scripts import stage1_enqueue


class Stage1EnqueueScriptTests(unittest.TestCase):
    @patch("scripts.stage1_enqueue.urlopen")
    def test_enqueue_stage1_run_posts_payload(self, mock_urlopen: MagicMock) -> None:
        response = MagicMock()
        response.read.return_value = json.dumps({"run_id": "ftpbg_test", "status": "queued"}).encode(
            "utf-8"
        )
        response.__enter__.return_value = response
        mock_urlopen.return_value = response

        result = stage1_enqueue.enqueue_stage1_run(
            base_url="http://127.0.0.1:8765",
            api_key="dev-key",
            payload={"name": "weekly-stage1", "base_model": "ollama:deepseek-coder", "min_samples": 10},
            timeout=5,
        )
        self.assertEqual(result["run_id"], "ftpbg_test")
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.get_method(), "POST")
        self.assertIn("/api/finetune/pipeline/stage1-runs", request.full_url)
        self.assertEqual(request.get_header("X-api-key"), "dev-key")


class Stage1SchedulerServiceTests(unittest.TestCase):
    def _build_scheduler(self, root: Path) -> Stage1SchedulerService:
        feedback_path = root / "feedback.jsonl"
        feedback_path.write_text(
            json.dumps({"rating": 5, "message": "Great routing suggestion"}) + "\n",
            encoding="utf-8",
        )
        settings = replace(
            get_settings(),
            code_model="ollama:deepseek-coder",
            stage1_schedule_enabled=True,
            stage1_schedule_weekday=0,
            stage1_schedule_hour=3,
            stage1_schedule_minute=0,
            stage1_schedule_min_samples=1,
            stage1_schedule_state_path=str(root / "schedule_state.json"),
            finetune_datasets_dir=str(root / "datasets"),
            finetune_jobs_path=str(root / "jobs.json"),
            finetune_adapters_path=str(root / "adapters.json"),
            finetune_pipelines_path=str(root / "pipelines.json"),
            feedback_file_path=str(feedback_path),
            task_sqlite_path=str(root / "tasks.db"),
            agent_run_sqlite_path=str(root / "agent_runs.db"),
        )
        finetune_service = FinetuneService(
            datasets_dir=settings.finetune_datasets_dir,
            jobs_path=settings.finetune_jobs_path,
            adapters_path=settings.finetune_adapters_path,
            pipelines_path=settings.finetune_pipelines_path,
            feedback_file_path=settings.feedback_file_path,
            task_sqlite_path=settings.task_sqlite_path,
            agent_run_sqlite_path=settings.agent_run_sqlite_path,
        )
        eval_service = MagicMock()
        eval_service.run_suite.return_value = {
            "run_id": "eval_test",
            "pass_rate": 1.0,
            "total": 1,
            "passed": 1,
        }
        return Stage1SchedulerService(
            settings=settings,
            finetune_service=finetune_service,
            eval_service=eval_service,
        )

    def test_should_run_for_time_blocks_duplicate_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = self._build_scheduler(Path(tmp))
            monday = datetime(2026, 6, 1, 3, 0, tzinfo=timezone.utc)
            self.assertTrue(scheduler.should_run_for_time(monday))
            scheduler._write_state({"slot": "2026-06-01T03:00", "run_id": "ftpbg_x"})
            self.assertFalse(scheduler.should_run_for_time(monday))

    def test_trigger_now_enqueues_pipeline_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scheduler = self._build_scheduler(Path(tmp))
            queued = scheduler.trigger_now()
            self.assertIn("run_id", queued)
            run_id = str(queued["run_id"])
            terminal = {"completed", "failed", "cancelled"}
            deadline = time.time() + 5.0
            run = None
            while time.time() < deadline:
                run = scheduler._finetune_service.get_stage1_pipeline_run(run_id)
                if run is not None and run["status"] in terminal:
                    break
                time.sleep(0.05)
            assert run is not None
            self.assertIn(run["status"], terminal)


if __name__ == "__main__":
    unittest.main()
