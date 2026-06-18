"""Tests for model-bound eval scenarios and gates."""

from __future__ import annotations

import unittest

from app.services.eval_ci_gate import MODEL_BOUND_CI_GATE, evaluate_tier_gate
from app.services.eval_service import EvalService
from app.services.tooling_service import ToolingService


class ModelBoundEvalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = EvalService(
            scenarios_path="./data/eval_scenarios.json",
            tooling_service=ToolingService(root_path="."),
            extra_scenarios_paths=["./data/eval_scenarios_humaneval.json"],
            model_benchmark_scenarios_path="./data/eval_scenarios_model_benchmark.json",
        )

    def test_model_bound_tool_ids(self) -> None:
        self.assertEqual(
            self.service.model_bound_tool_scenario_ids(),
            ["HE1", "HE2", "MBPP1", "MBPP2"],
        )

    def test_model_bound_all_ids(self) -> None:
        self.assertEqual(
            self.service.model_bound_scenario_ids(),
            ["MB1", "MB2", "MB3", "MT1", "MT2", "HE1", "HE2", "MBPP1", "MBPP2"],
        )

    def test_humaneval_patch_verify_passes(self) -> None:
        result = self.service.run_scenario("HE1")
        self.assertEqual(result["status"], "passed")

    def test_mbpp_exec_passes(self) -> None:
        result = self.service.run_scenario("MBPP1")
        self.assertEqual(result["status"], "passed")

    def test_model_bound_ci_gate_passes_on_tool_slice(self) -> None:
        report = self.service.run_scenario_ids(
            self.service.model_bound_tool_scenario_ids(),
            persist_report=False,
            category_filter="model_bound",
        )
        ok, message = evaluate_tier_gate(
            tier=MODEL_BOUND_CI_GATE,
            pass_rate=float(report["pass_rate"]),
            total=int(report["total"]),
        )
        self.assertTrue(ok, message)
        self.assertEqual(int(report["total"]), 4)


if __name__ == "__main__":
    unittest.main()
