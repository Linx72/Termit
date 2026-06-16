from __future__ import annotations

import unittest

from scripts.flaky_watch_report import IterationResult, build_report


class FlakyWatchReportTests(unittest.TestCase):
    def test_build_report_flags_flaky_suite(self) -> None:
        results = [
            IterationResult(
                suite="tests.test_agents_api",
                iteration=1,
                passed=True,
                duration_seconds=1.2,
                returncode=0,
                output_tail="ok",
            ),
            IterationResult(
                suite="tests.test_agents_api",
                iteration=2,
                passed=False,
                duration_seconds=1.5,
                returncode=1,
                output_tail="failed",
            ),
            IterationResult(
                suite="tests.test_platform_e2e",
                iteration=1,
                passed=True,
                duration_seconds=2.0,
                returncode=0,
                output_tail="ok",
            ),
        ]
        report = build_report(results)
        self.assertEqual(report["total_iterations"], 3)
        self.assertEqual(report["failed_iterations"], 1)
        self.assertTrue(report["flaky_suspected"])
        suites = report["suites"]
        assert isinstance(suites, list)
        agents_row = next(item for item in suites if item["suite"] == "tests.test_agents_api")
        self.assertEqual(agents_row["passed"], 1)
        self.assertEqual(agents_row["failed"], 1)


if __name__ == "__main__":
    unittest.main()
