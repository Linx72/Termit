"""Tests for model-aware eval runner and benchmark compare."""

from __future__ import annotations

import unittest
import tempfile
import json
from pathlib import Path

from app.services.eval_benchmark_service import EvalBenchmarkService
from app.services.eval_service import EvalService


class _ModelAwareLlmCaller:
    """Returns different quality per model for A/B benchmark tests."""

    def call(self, model_name: str, prompt: str, *, system: str = "") -> str:
        model = model_name.lower()
        if "eval_ok" in prompt.lower():
            return "EVAL_OK" if "termit" in model or "core" in model else "WRONG"
        if "17+25" in prompt:
            return "42" if "qwen" in model or "deepseek" in model or "termit" in model or "core" in model else "41"
        if "def add" in prompt.lower():
            return "def add(a, b): return a + b" if "instruct" in model or "termit" in model or "core" in model else "def add(a,b): pass"
        if "is_even" in prompt.lower():
            if "termit" in model or "core" in model:
                return "def is_even(n): return n % 2 == 0"
            return "I cannot write code for this task."
        if "a-b instead" in prompt.lower() or "a+b" in prompt.lower():
            return "return a + b" if "termit" in model or "core" in model or "qwen" in model else "return a - b"
        return "unknown"


class EvalModelRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = EvalService(
            scenarios_path="./data/eval_scenarios.json",
            llm_caller=_ModelAwareLlmCaller(),  # type: ignore[arg-type]
            model_benchmark_scenarios_path="./data/eval_scenarios_model_benchmark.json",
        )

    def test_model_benchmark_scenarios_loaded(self) -> None:
        ids = self.service.model_benchmark_scenario_ids()
        self.assertEqual(ids, ["MB1", "MB2", "MB3", "MT1", "MT2"])

    def test_task_runner_with_model_uses_llm_path(self) -> None:
        result = self.service.run_scenario("MT1", model="ollama:termit-core-ft")
        self.assertEqual(result["status"], "passed")
        self.assertIn("def is_even", str(result["message"]).lower())

    def test_task_runner_weak_model_fails_mt1(self) -> None:
        result = self.service.run_scenario("MT1", model="ollama:weak-model")
        self.assertEqual(result["status"], "failed")

    def test_benchmark_includes_task_runner_scenarios(self) -> None:
        benchmark = EvalBenchmarkService(
            termit_model="ollama:termit-core-ft",
            reference_model="ollama:weak-model",
            scenario_runner=lambda scenario_id, model: self.service.run_scenario(
                scenario_id,
                model=model,
            ),
        )
        report = benchmark.compare_on_scenarios(["MT1", "MT2"], persist=False)
        self.assertGreater(report["termit_pass_rate"], report["reference_pass_rate"])

    def test_model_llm_runner_passes_with_matching_model(self) -> None:
        result = self.service.run_scenario("MB1", model="ollama:termit-core-ft")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["model"], "ollama:termit-core-ft")
        self.assertIn("EVAL_OK", str(result["message"]))

    def test_model_llm_runner_fails_with_weak_model(self) -> None:
        result = self.service.run_scenario("MB1", model="ollama:weak-model")
        self.assertEqual(result["status"], "failed")

    def test_model_llm_requires_model_parameter(self) -> None:
        result = self.service.run_scenario("MB1")
        self.assertEqual(result["status"], "failed")
        self.assertIn("model", str(result["message"]).lower())

    def test_benchmark_compare_produces_different_pass_rates(self) -> None:
        benchmark = EvalBenchmarkService(
            termit_model="ollama:termit-core-ft",
            reference_model="ollama:weak-model",
            scenario_runner=lambda scenario_id, model: self.service.run_scenario(
                scenario_id,
                model=model,
            ),
        )
        report = benchmark.compare_on_scenarios(["MB1", "MB2"], persist=False)
        self.assertGreater(report["termit_pass_rate"], report["reference_pass_rate"])
        models = {row["model"] for row in report["rows"]}
        self.assertIn("ollama:termit-core-ft", models)
        self.assertIn("ollama:weak-model", models)

    def test_capability_review_aggregates_recent_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_file = Path(tmp) / "eval_reports.jsonl"
            entries = [
                {
                    "benchmark_id": "bench_1",
                    "timestamp": "2026-06-01T00:00:00Z",
                    "termit_pass_rate": 0.6,
                    "reference_pass_rate": 0.8,
                    "termit_quality_mean": 0.5,
                    "reference_quality_mean": 0.6,
                    "rows": [{"scenario_id": "MB1"}],
                },
                {
                    "benchmark_id": "bench_2",
                    "timestamp": "2026-06-08T00:00:00Z",
                    "termit_pass_rate": 0.9,
                    "reference_pass_rate": 0.8,
                    "termit_quality_mean": 0.75,
                    "reference_quality_mean": 0.7,
                    "rows": [{"scenario_id": "MB2"}],
                },
            ]
            report_file.write_text(
                "\n".join(json.dumps(item) for item in entries) + "\n",
                encoding="utf-8",
            )
            benchmark = EvalBenchmarkService(
                report_file_path=str(report_file),
                termit_model="ollama:termit-core-ft",
                reference_model="ollama:weak-model",
            )
            review = benchmark.build_capability_review(limit=8)
            self.assertEqual(review["total_reports"], 2)
            self.assertEqual(review["latest_benchmark_id"], "bench_2")
            self.assertEqual(review["trend_direction"], "improving")
            self.assertGreater(float(review["mean_pass_gap"]), -0.2)
            self.assertAlmostEqual(float(review["termit_win_rate"]), 0.5, places=4)

    def test_capability_regression_compares_with_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_file = Path(tmp) / "eval_reports.jsonl"
            entries = [
                {
                    "benchmark_id": "bench_1",
                    "timestamp": "2026-06-01T00:00:00Z",
                    "termit_pass_rate": 0.5,
                    "reference_pass_rate": 0.6,
                    "termit_quality_mean": 0.6,
                    "reference_quality_mean": 0.7,
                    "rows": [{"scenario_id": "MB1"}],
                },
                {
                    "benchmark_id": "bench_2",
                    "timestamp": "2026-06-08T00:00:00Z",
                    "termit_pass_rate": 0.8,
                    "reference_pass_rate": 0.7,
                    "termit_quality_mean": 0.8,
                    "reference_quality_mean": 0.75,
                    "rows": [{"scenario_id": "MB2"}],
                },
            ]
            report_file.write_text(
                "\n".join(json.dumps(item) for item in entries) + "\n",
                encoding="utf-8",
            )
            baseline = {
                "total_reports": 2,
                "mean_pass_gap": -0.08,
                "mean_quality_gap": -0.06,
                "termit_win_rate": 0.45,
            }
            benchmark = EvalBenchmarkService(
                report_file_path=str(report_file),
                termit_model="ollama:termit-core-ft",
                reference_model="ollama:weak-model",
            )
            regression = benchmark.build_capability_regression(
                baseline=baseline,
                limit=8,
                max_pass_gap_drop=0.05,
                max_quality_gap_drop=0.05,
                max_win_rate_drop=0.1,
            )
            self.assertTrue(bool(regression["gate_passed"]))
            self.assertEqual(regression["current_trend_direction"], "improving")

    def test_refresh_capability_baseline_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_file = Path(tmp) / "eval_reports.jsonl"
            baseline_file = Path(tmp) / "capability_baseline.json"
            report_file.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "benchmark_id": "bench_1",
                                "timestamp": "2026-06-01T00:00:00Z",
                                "termit_pass_rate": 0.7,
                                "reference_pass_rate": 0.6,
                                "termit_quality_mean": 0.8,
                                "reference_quality_mean": 0.7,
                                "rows": [{"scenario_id": "MB1"}],
                            }
                        ),
                        json.dumps(
                            {
                                "benchmark_id": "bench_2",
                                "timestamp": "2026-06-08T00:00:00Z",
                                "termit_pass_rate": 0.6,
                                "reference_pass_rate": 0.6,
                                "termit_quality_mean": 0.7,
                                "reference_quality_mean": 0.6,
                                "rows": [{"scenario_id": "MB2"}],
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            benchmark = EvalBenchmarkService(
                report_file_path=str(report_file),
                termit_model="ollama:termit-core-ft",
                reference_model="ollama:weak-model",
            )
            baseline = benchmark.refresh_capability_baseline(
                baseline_file_path=str(baseline_file),
                limit=12,
            )
            self.assertTrue(baseline_file.exists())
            saved = json.loads(baseline_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["total_reports"], 2)
            self.assertEqual(saved["latest_benchmark_id"], "bench_2")
            self.assertAlmostEqual(float(baseline["termit_win_rate"]), 0.5, places=4)


if __name__ == "__main__":
    unittest.main()
