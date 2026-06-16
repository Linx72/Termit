from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.domain.schemas import FinetuneDpoExportRequest
from app.main import app
from app.services.finetune_service import FinetuneService
from app.services.training_signal_store import TrainingSignalStore


class FinetunePipelineE2ETests(unittest.TestCase):
    def test_dpo_export_endpoint_with_seeded_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            signals_path = root / "signals.jsonl"
            store = TrainingSignalStore(str(signals_path), min_output_chars=8, enabled=True)
            instruction = "Resolve verify command for patch loop"
            store.try_capture_tool_step(
                run_id="e2e-pos",
                step=1,
                action="tool",
                tool="apply_patch",
                observation="verify passed using resolve_verify_command from repo root",
                instruction=instruction,
                verified=True,
            )
            store.try_capture_negative_tool_step(
                run_id="e2e-neg",
                step=2,
                action="tool",
                tool="apply_patch",
                observation="Tool error: verify failed because cwd was wrong",
                instruction=instruction,
                reason="verify_failed",
            )

            service = FinetuneService(
                datasets_dir=str(root / "datasets"),
                jobs_path=str(root / "jobs.json"),
                adapters_path=str(root / "adapters.json"),
                feedback_file_path=str(root / "feedback.jsonl"),
                task_sqlite_path=str(root / "tasks.db"),
                agent_run_sqlite_path=str(root / "runs.db"),
                memory_sqlite_path=str(root / "memory.db"),
                training_signals_path=str(signals_path),
                training_signal_store=store,
            )
            result = service.export_dpo_dataset(
                FinetuneDpoExportRequest(name="e2e-dpo", min_pairs=1, min_chosen_chars=8)
            )
            self.assertEqual(result["format"], "dpo_jsonl")
            self.assertGreaterEqual(result["pair_count"], 1)
            row = json.loads(Path(str(result["dataset_path"])).read_text(encoding="utf-8").splitlines()[0])
            self.assertIn("chosen", row)
            self.assertIn("rejected", row)

    def test_tuning_report_http(self) -> None:
        client = TestClient(app)
        response = client.get("/api/finetune/training/tuning-report")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("recommendations", body)

    def test_adapter_resolve_http(self) -> None:
        client = TestClient(app)
        response = client.get("/api/finetune/adapters/resolve", params={"repo_profile_id": "termit-core"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("model", response.json())

    def test_validate_dpo_endpoint_exists(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/api/finetune/datasets/validate-dpo",
            json={"dataset_path": "/tmp/does-not-exist.jsonl", "min_text_chars": 4},
        )
        self.assertEqual(response.status_code, 400)

    def test_train_dpo_endpoint_exists(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/api/finetune/datasets/train-dpo",
            params={
                "dataset_path": "/tmp/does-not-exist.jsonl",
                "base_model": "ollama:deepseek-coder",
            },
            json={},
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
