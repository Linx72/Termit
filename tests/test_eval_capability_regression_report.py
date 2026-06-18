"""Tests for capability regression report script."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "eval_capability_regression_report.py"


class EvalCapabilityRegressionReportTests(unittest.TestCase):
    def test_detects_regression(self) -> None:
        baseline = {
            "total_reports": 3,
            "mean_pass_gap": 0.10,
            "mean_quality_gap": 0.10,
            "termit_win_rate": 0.8,
            "trend_direction": "improving",
        }
        current = {
            "total_reports": 3,
            "mean_pass_gap": -0.20,
            "mean_quality_gap": -0.10,
            "termit_win_rate": 0.2,
            "trend_direction": "regressing",
        }
        with tempfile.TemporaryDirectory() as tmp:
            base_path = Path(tmp) / "baseline.json"
            cur_path = Path(tmp) / "current.json"
            base_path.write_text(json.dumps(baseline), encoding="utf-8")
            cur_path.write_text(json.dumps(current), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--baseline",
                    str(base_path),
                    "--current",
                    str(cur_path),
                    "--max-pass-gap-drop",
                    "0.05",
                    "--max-quality-gap-drop",
                    "0.05",
                    "--max-win-rate-drop",
                    "0.10",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn('"gate_passed": false', proc.stdout)

    def test_passes_within_tolerance(self) -> None:
        baseline = {
            "total_reports": 2,
            "mean_pass_gap": 0.00,
            "mean_quality_gap": 0.00,
            "termit_win_rate": 0.4,
            "trend_direction": "flat",
        }
        current = {
            "total_reports": 4,
            "mean_pass_gap": -0.03,
            "mean_quality_gap": -0.04,
            "termit_win_rate": 0.35,
            "trend_direction": "flat",
        }
        with tempfile.TemporaryDirectory() as tmp:
            base_path = Path(tmp) / "baseline.json"
            cur_path = Path(tmp) / "current.json"
            base_path.write_text(json.dumps(baseline), encoding="utf-8")
            cur_path.write_text(json.dumps(current), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--baseline",
                    str(base_path),
                    "--current",
                    str(cur_path),
                    "--max-pass-gap-drop",
                    "0.05",
                    "--max-quality-gap-drop",
                    "0.05",
                    "--max-win-rate-drop",
                    "0.10",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn('"gate_passed": true', proc.stdout)


if __name__ == "__main__":
    unittest.main()
