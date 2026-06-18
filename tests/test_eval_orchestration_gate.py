from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE_SCRIPT = ROOT / "scripts" / "eval_orchestration_gate.py"


def _run_gate(report: dict[str, object], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    merged_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("TERMIT_ORCH_")
    }
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


class EvalOrchestrationGateTests(unittest.TestCase):
    def test_gate_passes_when_thresholds_met(self) -> None:
        report = {
            "total": 3,
            "pass_rate": 0.6,
            "metrics_after": {"coder_retry_success_rate": 0.5},
        }
        result = _run_gate(
            report,
            {
                "TERMIT_ORCH_GATE_TIER": "release",
                "TERMIT_ORCH_MIN_PASS_RATE": "0.5",
                "TERMIT_ORCH_MIN_RETRY_SUCCESS_RATE": "0.4",
                "TERMIT_ORCH_MIN_TOTAL": "3",
            },
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("gate passed", result.stdout)

    def test_gate_fails_on_retry_success_threshold(self) -> None:
        report = {
            "total": 3,
            "pass_rate": 0.7,
            "metrics_after": {"coder_retry_success_rate": 0.2},
        }
        result = _run_gate(
            report,
            {
                "TERMIT_ORCH_MIN_PASS_RATE": "0.5",
                "TERMIT_ORCH_MIN_RETRY_SUCCESS_RATE": "0.3",
                "TERMIT_ORCH_MIN_TOTAL": "3",
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("retry_success_rate", result.stdout)

    def test_gate_fails_on_min_total(self) -> None:
        report = {
            "total": 1,
            "pass_rate": 1.0,
            "metrics_after": {"coder_retry_success_rate": 1.0},
        }
        result = _run_gate(
            report,
            {
                "TERMIT_ORCH_MIN_PASS_RATE": "0.5",
                "TERMIT_ORCH_MIN_RETRY_SUCCESS_RATE": "0.1",
                "TERMIT_ORCH_MIN_TOTAL": "2",
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("total=", result.stdout)


if __name__ == "__main__":
    unittest.main()
