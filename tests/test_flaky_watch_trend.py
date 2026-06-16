from __future__ import annotations

import unittest

from scripts.flaky_watch_trend import _to_markdown, build_trend


class FlakyWatchTrendTests(unittest.TestCase):
    def test_build_trend_with_baseline(self) -> None:
        current = {
            "total_iterations": 10,
            "pass_rate": 0.9,
            "suites": [
                {"suite": "tests.test_agents_api", "pass_rate": 0.8, "duration_mean_seconds": 2.5},
                {"suite": "tests.test_platform_e2e", "pass_rate": 1.0, "duration_mean_seconds": 3.0},
            ],
        }
        baseline = {
            "total_iterations": 10,
            "pass_rate": 0.8,
            "suites": [
                {"suite": "tests.test_agents_api", "pass_rate": 0.6, "duration_mean_seconds": 2.0},
                {"suite": "tests.test_platform_e2e", "pass_rate": 1.0, "duration_mean_seconds": 3.5},
            ],
        }
        trend = build_trend(
            current=current,
            baseline=baseline,
            baseline_status="available",
            baseline_note="baseline fetched from artifact",
        )
        self.assertTrue(trend["baseline_available"])
        self.assertEqual(trend["baseline_status"], "available")
        self.assertEqual(trend["baseline_note"], "baseline fetched from artifact")
        self.assertEqual(trend["overall_trend"], "improved")
        self.assertEqual(trend["improved_suites"], 2)
        self.assertEqual(trend["regressed_suites"], 0)
        suites = {row["suite"]: row for row in trend["suites"]}
        self.assertEqual(suites["tests.test_agents_api"]["trend"], "improved")
        self.assertEqual(suites["tests.test_platform_e2e"]["trend"], "improved")
        self.assertEqual(suites["tests.test_agents_api"]["pass_rate_delta"], 0.2)
        self.assertEqual(suites["tests.test_agents_api"]["duration_mean_delta_seconds"], 0.5)
        self.assertEqual(suites["tests.test_platform_e2e"]["pass_rate_delta"], 0.0)
        self.assertEqual(suites["tests.test_platform_e2e"]["duration_mean_delta_seconds"], -0.5)

    def test_build_trend_without_baseline(self) -> None:
        current = {
            "total_iterations": 2,
            "pass_rate": 1.0,
            "suites": [{"suite": "tests.test_agents_api", "pass_rate": 1.0, "duration_mean_seconds": 1.0}],
        }
        trend = build_trend(
            current=current,
            baseline=None,
            baseline_status="missing",
            baseline_note="no previous artifact",
        )
        self.assertFalse(trend["baseline_available"])
        self.assertEqual(trend["baseline_status"], "missing")
        self.assertEqual(trend["baseline_note"], "no previous artifact")
        self.assertEqual(trend["overall_trend"], "stable")
        row = trend["suites"][0]
        self.assertEqual(row["trend"], "unknown")
        self.assertIsNone(row["pass_rate_delta"])
        self.assertIsNone(row["duration_mean_delta_seconds"])

    def test_build_trend_marks_regression(self) -> None:
        current = {
            "total_iterations": 2,
            "pass_rate": 0.5,
            "suites": [{"suite": "tests.test_agents_api", "pass_rate": 0.5, "duration_mean_seconds": 2.0}],
        }
        baseline = {
            "total_iterations": 2,
            "pass_rate": 1.0,
            "suites": [{"suite": "tests.test_agents_api", "pass_rate": 1.0, "duration_mean_seconds": 1.8}],
        }
        trend = build_trend(current=current, baseline=baseline)
        self.assertEqual(trend["overall_trend"], "regressed")
        self.assertEqual(trend["regressed_suites"], 1)
        row = trend["suites"][0]
        self.assertEqual(row["trend"], "regressed")

    def test_markdown_includes_overall_trend_regressed(self) -> None:
        trend = {
            "overall_trend": "regressed",
            "improved_suites": 0,
            "regressed_suites": 1,
            "stable_suites": 0,
            "baseline_available": True,
            "baseline_status": "available",
            "current_total_iterations": 2,
            "current_pass_rate": 0.5,
            "baseline_total_iterations": 2,
            "baseline_pass_rate": 1.0,
            "suites": [
                {
                    "suite": "tests.test_agents_api",
                    "trend": "regressed",
                    "pass_rate_delta": -0.5,
                    "duration_mean_delta_seconds": 0.2,
                }
            ],
        }
        md = _to_markdown(trend)
        self.assertIn("- overall_trend: regressed", md)
        self.assertIn("## tests.test_agents_api", md)


if __name__ == "__main__":
    unittest.main()
