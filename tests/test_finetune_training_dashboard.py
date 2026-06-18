import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.finetune_service import FinetuneService
from app.services.training_signal_store import TrainingSignalStore


class FinetuneTrainingDashboardApiTests(unittest.TestCase):
    def test_training_dashboard_endpoint(self) -> None:
        client = TestClient(app)
        response = client.get("/api/finetune/training/dashboard?limit=3")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("training_signals_count", payload)
        self.assertIn("eval_trend", payload)
        self.assertIn("tuning_report", payload)
        self.assertIn("eval_improvement_kpi", payload)

    def test_dpo_status_endpoint(self) -> None:
        client = TestClient(app)
        response = client.get("/api/finetune/dpo/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("pair_count_estimate", payload)
        self.assertIn("contract_valid", payload)
        self.assertIn("signals_file", payload)

    def test_tuning_report_endpoint(self) -> None:
        client = TestClient(app)
        response = client.get("/api/finetune/training/tuning-report?event_limit=500")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("recommendations", payload)
        self.assertIn("event_stats", payload)

    def test_load_eval_improvement_kpi_merges_baseline_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "eval_kpi_last.json").write_text(
                json.dumps({"kpi_passed": False, "current_pass_rate": 0.5}),
                encoding="utf-8",
            )
            (data_dir / "eval_kpi_baseline.json").write_text(
                json.dumps(
                    {
                        "pass_rate": 1.0,
                        "eval_model": "ollama:deepseek-coder",
                        "scenario_ids": ["MB1", "MB2"],
                    }
                ),
                encoding="utf-8",
            )
            service = FinetuneService(
                datasets_dir=str(root / "datasets"),
                jobs_path=str(root / "jobs.json"),
                adapters_path=str(root / "adapters.json"),
                eval_report_file_path=str(data_dir / "eval_reports.jsonl"),
            )
            kpi = service._load_eval_improvement_kpi()
            assert kpi is not None
            self.assertEqual(kpi.get("baseline_eval_model"), "ollama:deepseek-coder")
            self.assertEqual(kpi.get("baseline_pass_rate"), 1.0)
            self.assertEqual(kpi.get("scenario_ids"), ["MB1", "MB2"])

    def test_export_includes_verified_tool_step_sft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals_path = root / "signals.jsonl"
            store = TrainingSignalStore(str(signals_path), min_output_chars=8)
            store.try_capture_tool_step(
                run_id="run-verify-1",
                step=2,
                action="tool",
                tool="apply_patch",
                observation='{"applied":true,"verify":{"executed":true,"exit_code":0}}',
                instruction="Fix handler and verify tests",
                verified=True,
            )
            service = FinetuneService(
                datasets_dir=str(root / "datasets"),
                jobs_path=str(root / "jobs.json"),
                adapters_path=str(root / "adapters.json"),
                cycle_events_path=str(root / "stage1_cycle_events.jsonl"),
                feedback_file_path=str(root / "feedback.jsonl"),
                task_sqlite_path=str(root / "tasks.db"),
                agent_run_sqlite_path=str(root / "runs.db"),
                repo_profiles_path=str(root / "profiles.json"),
                memory_sqlite_path=str(root / "memory.db"),
                training_signal_store=store,
            )
            from app.domain.schemas import FinetuneDatasetExportRequest

            result = service.export_dataset(
                FinetuneDatasetExportRequest(
                    name="verified-sft",
                    min_samples=1,
                    include_feedback=False,
                    include_tasks=False,
                    include_agent_runs=False,
                    include_chat_sessions=False,
                    include_training_signals=True,
                    include_dpo_negatives=False,
                )
            )
            rows = [
                json.loads(line)
                for line in Path(str(result["dataset_path"])).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertGreaterEqual(len(rows), 1)
            self.assertTrue(any("apply_patch" in row.get("input", "") or "verify" in row.get("output", "") for row in rows))

    def test_training_dashboard_includes_signal_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals_path = root / "signals.jsonl"
            store = TrainingSignalStore(str(signals_path), min_output_chars=8)
            store.try_capture_agent_run(
                run_id="dash-run-1",
                instruction="Explain module layout",
                response="The module exports helper functions for routing.",
            )
            service = FinetuneService(
                datasets_dir=str(root / "datasets"),
                jobs_path=str(root / "jobs.json"),
                adapters_path=str(root / "adapters.json"),
                cycle_events_path=str(root / "stage1_cycle_events.jsonl"),
                feedback_file_path=str(root / "feedback.jsonl"),
                task_sqlite_path=str(root / "tasks.db"),
                agent_run_sqlite_path=str(root / "runs.db"),
                repo_profiles_path=str(root / "profiles.json"),
                memory_sqlite_path=str(root / "memory.db"),
                training_signal_store=store,
            )
            dashboard = service.training_dashboard(limit=3)
            self.assertGreaterEqual(int(dashboard["training_signals_count"]), 1)


if __name__ == "__main__":
    unittest.main()
