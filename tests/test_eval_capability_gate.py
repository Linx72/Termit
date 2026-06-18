from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE_SCRIPT = ROOT / "scripts" / "eval_capability_gate.py"


def _run_gate(report: dict[str, object], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    merged_env.update(env)
    return subprocess.run(
        ["python3", str(GATE_SCRIPT)],
        input=json.dumps(report),
        text=True,
        capture_output=True,
        env=merged_env,
        cwd=str(ROOT),
        check=False,
    )


class EvalCapabilityGateTests(unittest.TestCase):
    def test_gate_passes_within_thresholds(self) -> None:
        report = {
            "total_reports": 4,
            "mean_pass_gap": -0.01,
            "mean_quality_gap": -0.05,
            "termit_win_rate": 0.5,
            "trend_direction": "flat",
        }
        result = _run_gate(
            report,
            {
                "TERMIT_CAP_MIN_REPORTS": "3",
                "TERMIT_CAP_MIN_MEAN_PASS_GAP": "-0.05",
                "TERMIT_CAP_MIN_MEAN_QUALITY_GAP": "-0.10",
                "TERMIT_CAP_MIN_WIN_RATE": "0.40",
                "TERMIT_CAP_ALLOWED_TRENDS": "flat,improving",
            },
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Capability gate passed", result.stdout)

    def test_gate_fails_when_pass_gap_too_low(self) -> None:
        report = {
            "total_reports": 4,
            "mean_pass_gap": -0.30,
            "mean_quality_gap": 0.00,
            "termit_win_rate": 0.5,
            "trend_direction": "improving",
        }
        result = _run_gate(
            report,
            {
                "TERMIT_CAP_MIN_REPORTS": "2",
                "TERMIT_CAP_MIN_MEAN_PASS_GAP": "-0.05",
                "TERMIT_CAP_MIN_MEAN_QUALITY_GAP": "-0.10",
                "TERMIT_CAP_MIN_WIN_RATE": "0.40",
                "TERMIT_CAP_ALLOWED_TRENDS": "flat,improving",
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("mean_pass_gap", result.stdout)

    def test_gate_fails_when_trend_not_allowed(self) -> None:
        report = {
            "total_reports": 5,
            "mean_pass_gap": 0.02,
            "mean_quality_gap": 0.01,
            "termit_win_rate": 0.6,
            "trend_direction": "regressing",
        }
        result = _run_gate(
            report,
            {
                "TERMIT_CAP_MIN_REPORTS": "2",
                "TERMIT_CAP_MIN_MEAN_PASS_GAP": "-0.05",
                "TERMIT_CAP_MIN_MEAN_QUALITY_GAP": "-0.10",
                "TERMIT_CAP_MIN_WIN_RATE": "0.40",
                "TERMIT_CAP_ALLOWED_TRENDS": "flat,improving",
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("trend_direction", result.stdout)


if __name__ == "__main__":
    unittest.main()
