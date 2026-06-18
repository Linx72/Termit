"""Tests for capability quarterly review shell script."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "capability_quarterly_review.sh"


class CapabilityQuarterlyReviewScriptTests(unittest.TestCase):
    def test_script_passes_with_ci_safe_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "eval_reports.jsonl"
            baseline_path = Path(tmp) / "baseline.json"
            review_out = Path(tmp) / "review.json"
            regression_out = Path(tmp) / "regression.json"
            report_path.write_text(
                json.dumps(
                    {
                        "benchmark_id": "bench_q1",
                        "timestamp": "2026-06-10T00:00:00Z",
                        "termit_pass_rate": 0.7,
                        "reference_pass_rate": 0.6,
                        "termit_quality_mean": 0.8,
                        "reference_quality_mean": 0.7,
                        "rows": [{"scenario_id": "MB1", "status": "passed"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            baseline_path.write_text(
                json.dumps(
                    {
                        "total_reports": 1,
                        "mean_pass_gap": 0.0,
                        "mean_quality_gap": 0.0,
                        "termit_win_rate": 0.0,
                        "trend_direction": "flat",
                    }
                ),
                encoding="utf-8",
            )
            env = {
                "TERMIT_EVAL_REPORT_FILE": str(report_path),
                "TERMIT_EVAL_CAPABILITY_BASELINE_PATH": str(baseline_path),
                "TERMIT_CAP_REVIEW_OUT": str(review_out),
                "TERMIT_CAP_REGRESSION_OUT": str(regression_out),
                "TERMIT_CAP_GATE_TIER": "ci",
            }
            proc = subprocess.run(
                ["bash", str(SCRIPT)],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
                env={**dict(**{k: v for k, v in __import__("os").environ.items()}), **env},
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stdout + proc.stderr)
            self.assertTrue(review_out.exists())
            self.assertTrue(regression_out.exists())
            regression = json.loads(regression_out.read_text(encoding="utf-8"))
            self.assertTrue(regression.get("gate_passed"))


if __name__ == "__main__":
    unittest.main()
