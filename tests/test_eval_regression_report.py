"""Tests for eval regression report script."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "eval_regression_report.py"


class EvalRegressionReportTests(unittest.TestCase):
    def test_detects_pass_rate_regression(self) -> None:
        baseline = {
            "pass_rate": 0.98,
            "total": 10,
            "results": [{"id": "A", "status": "passed"}],
        }
        current = {
            "pass_rate": 0.90,
            "total": 10,
            "results": [
                {"id": "A", "status": "passed"},
                {"id": "B", "status": "failed"},
            ],
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
                    "--max-pass-rate-drop",
                    "0.02",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 1)
            self.assertIn("new_failures", proc.stdout)

    def test_passes_within_tolerance(self) -> None:
        baseline = {"pass_rate": 0.97, "total": 5, "results": []}
        current = {"pass_rate": 0.96, "total": 5, "results": []}
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
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn('"gate_passed": true', proc.stdout)


if __name__ == "__main__":
    unittest.main()
