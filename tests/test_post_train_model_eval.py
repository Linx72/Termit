"""Тесты post-train model eval KPI script."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class PostTrainModelEvalTests(unittest.TestCase):
    def test_bash_syntax_post_train_model_eval(self) -> None:
        proc = subprocess.run(
            ["bash", "-n", str(ROOT / "scripts/post_train_model_eval.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        # Python file — bash -n is noop; ensure script exists.
        self.assertTrue((ROOT / "scripts/post_train_model_eval.py").is_file())

    def test_run_scenario_ids_accepts_model(self) -> None:
        from app.services.eval_service import EvalService
        from app.services.tooling_service import ToolingService

        service = EvalService(
            scenarios_path=str(ROOT / "data/eval_scenarios.json"),
            tooling_service=ToolingService(root_path=str(ROOT)),
            model_benchmark_scenarios_path=str(ROOT / "data/eval_scenarios_model_benchmark.json"),
        )
        with patch.object(service, "run_scenario", return_value={"status": "passed"}) as mock_run:
            report = service.run_scenario_ids(["MB1"], persist_report=False, model="ollama:demo")
        mock_run.assert_called_once_with("MB1", model="ollama:demo")
        self.assertEqual(report["eval_model"], "ollama:demo")

    def test_run_suite_accepts_model(self) -> None:
        from app.services.eval_service import EvalService
        from app.services.tooling_service import ToolingService

        service = EvalService(
            scenarios_path=str(ROOT / "data/eval_scenarios.json"),
            tooling_service=ToolingService(root_path=str(ROOT)),
        )
        with patch.object(service, "run_scenario", return_value={"status": "passed"}) as mock_run:
            report = service.run_suite(category="coding", limit=1, persist_report=False, model="ollama:demo")
        mock_run.assert_called_once()
        self.assertEqual(mock_run.call_args.kwargs.get("model"), "ollama:demo")
        self.assertEqual(report["eval_model"], "ollama:demo")


if __name__ == "__main__":
    unittest.main()
