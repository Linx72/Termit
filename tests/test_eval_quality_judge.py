"""Tests for eval quality judge and CI gate tiers."""

from __future__ import annotations

import unittest

from app.services.eval_ci_gate import DEEP_GATE, FAST_GATE, RELEASE_GATE, evaluate_tier_gate
from app.services.eval_quality_judge_service import EvalQualityJudgeService, heuristic_quality_score


class EvalQualityJudgeTests(unittest.TestCase):
    def test_heuristic_scores_failed_low(self) -> None:
        score = heuristic_quality_score(
            prompt="fix bug",
            response="",
            status="failed",
            task_success=0,
        )
        self.assertLessEqual(score.score, 1.5)

    def test_heuristic_scores_pass_higher(self) -> None:
        score = heuristic_quality_score(
            prompt="fix bug in app/main.py",
            response="Updated app/main.py and ran unittest verify.",
            status="passed",
            task_success=1,
        )
        self.assertGreaterEqual(score.score, 3.0)

    def test_judge_service_summary(self) -> None:
        service = EvalQualityJudgeService()
        summary = service.summarize_scores([2.0, 3.0, 4.0, 5.0])
        self.assertEqual(summary["quality_count"], 4)
        self.assertGreaterEqual(float(summary["quality_median"]), 3.0)


class EvalCiGateTierTests(unittest.TestCase):
    def test_fast_gate_passes(self) -> None:
        ok, _ = evaluate_tier_gate(
            tier=FAST_GATE,
            pass_rate=0.92,
            total=12,
            quality_median=2.5,
        )
        self.assertTrue(ok)

    def test_release_gate_blocks_low_quality(self) -> None:
        ok, detail = evaluate_tier_gate(
            tier=RELEASE_GATE,
            pass_rate=0.96,
            total=40,
            quality_median=2.5,
        )
        self.assertFalse(ok)
        self.assertIn("quality_median", detail)

    def test_deep_gate_threshold(self) -> None:
        ok, _ = evaluate_tier_gate(
            tier=DEEP_GATE,
            pass_rate=0.95,
            total=53,
            quality_median=None,
        )
        self.assertTrue(ok)

    def test_release_gate_blocks_heuristic_only_coverage(self) -> None:
        ok, detail = evaluate_tier_gate(
            tier=RELEASE_GATE,
            pass_rate=0.99,
            total=40,
            quality_median=4.2,
            cloud_judge_coverage=0.0,
        )
        self.assertFalse(ok)
        self.assertIn("cloud_judge_coverage", detail)


if __name__ == "__main__":
    unittest.main()
