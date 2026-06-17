import json
import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import TaskType
from app.services.routing_benchmark_sync_service import (
    RoutingBenchmarkSyncService,
    category_to_task_type,
    compute_model_task_scores,
    load_latest_benchmark_report,
)
from app.services.routing_policy_service import RoutingPolicyService


class RoutingBenchmarkSyncTests(unittest.TestCase):
    def test_category_to_task_type_mapping(self) -> None:
        self.assertEqual(category_to_task_type("coding"), "coding")
        self.assertEqual(category_to_task_type("cursor_parity"), "coding")
        self.assertEqual(category_to_task_type("local"), "debug")
        self.assertEqual(category_to_task_type("unknown"), "general")

    def test_compute_model_task_scores(self) -> None:
        rows = [
            {"scenario_id": "A1", "model": "ollama:termit-core-ft", "status": "passed"},
            {"scenario_id": "A2", "model": "ollama:termit-core-ft", "status": "failed"},
            {"scenario_id": "P4", "model": "ollama:deepseek-coder", "status": "passed"},
        ]
        categories = {"A1": "coding", "A2": "coding", "P4": "platform"}
        scores = compute_model_task_scores(rows, category_by_scenario_id=categories)
        self.assertAlmostEqual(scores["ollama:termit-core-ft"]["coding"], 0.5)
        self.assertAlmostEqual(scores["ollama:deepseek-coder"]["general"], 1.0)

    def test_load_latest_benchmark_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reports.jsonl"
            path.write_text(
                json.dumps({"run_id": "eval_1", "total": 3}) + "\n"
                + json.dumps(
                    {
                        "benchmark_id": "bench_old",
                        "rows": [{"scenario_id": "A1", "model": "m1", "status": "passed"}],
                    }
                )
                + "\n"
                + json.dumps(
                    {
                        "benchmark_id": "bench_new",
                        "rows": [{"scenario_id": "A1", "model": "m2", "status": "failed"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            latest = load_latest_benchmark_report(path)
            self.assertIsNotNone(latest)
            assert latest is not None
            self.assertEqual(latest["benchmark_id"], "bench_new")

    def test_sync_updates_routing_benchmarks_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            benchmarks_path = Path(tmp) / "routing_benchmarks.json"
            benchmarks_path.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "updated_at": "2026-01-01",
                        "scores": {
                            "ollama:termit-core-ft": {"coding": 0.9, "general": 0.85},
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            routing = RoutingPolicyService(
                repo_profiles_path="./data/repo_model_profiles.json",
                benchmarks_path=str(benchmarks_path),
            )
            sync = RoutingBenchmarkSyncService(routing)
            report = {
                "benchmark_id": "bench_test",
                "rows": [
                    {
                        "scenario_id": "A1",
                        "model": "ollama:termit-core-ft",
                        "status": "passed",
                    },
                    {
                        "scenario_id": "A2",
                        "model": "ollama:termit-core-ft",
                        "status": "passed",
                    },
                ],
            }
            summary = sync.sync_from_report(
                report,
                category_by_scenario_id={"A1": "coding", "A2": "coding"},
                blend_alpha=1.0,
                persist=True,
            )
            self.assertIn("ollama:termit-core-ft", summary["updated_models"])
            saved = json.loads(benchmarks_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["version"], 3)
            self.assertAlmostEqual(
                saved["scores"]["ollama:termit-core-ft"]["coding"],
                1.0,
            )

    def test_routing_policy_blend_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            benchmarks_path = Path(tmp) / "routing_benchmarks.json"
            benchmarks_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "scores": {"m1": {"coding": 0.8}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            routing = RoutingPolicyService(
                repo_profiles_path="./data/repo_model_profiles.json",
                benchmarks_path=str(benchmarks_path),
            )
            routing.update_benchmark_scores({"m1": {"coding": 1.0}}, blend_alpha=0.5, persist=False)
            self.assertAlmostEqual(routing.benchmark_score("m1", TaskType.coding), 0.9)


if __name__ == "__main__":
    unittest.main()
