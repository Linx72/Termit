from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.orchestration_eval_report_store import OrchestrationEvalReportStore


class OrchestrationEvalReportStoreTests(unittest.TestCase):
    def test_append_and_trend_points(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orch_reports.jsonl"
            store = OrchestrationEvalReportStore(str(path))
            store.append_report(
                {
                    "total": 2,
                    "pass_rate": 0.5,
                    "metrics_after": {"coder_retry_success_rate": 0.25},
                }
            )
            store.append_report(
                {
                    "total": 3,
                    "pass_rate": 0.66,
                    "metrics_after": {"coder_retry_success_rate": 0.5},
                }
            )
            recent = store.list_recent(limit=5)
            self.assertEqual(len(recent), 2)
            trend = store.trend_points(limit=5)
            self.assertEqual(len(trend), 2)
            self.assertAlmostEqual(trend[-1]["retry_success_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
