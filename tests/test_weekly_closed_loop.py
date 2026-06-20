"""Tests for shadow traffic gate and weekly closed loop wiring."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ShadowTrafficGateTests(unittest.TestCase):
    def test_passes_when_shadow_and_regression_enabled(self) -> None:
        from scripts.shadow_traffic_gate import _evaluate

        ok, summary = _evaluate(
            {"shadow_traffic_percent": 10.0, "regression_gate_enabled": True},
            min_shadow=10.0,
        )
        self.assertTrue(ok)
        self.assertTrue(summary["gate_passed"])

    def test_fails_when_shadow_below_threshold(self) -> None:
        from scripts.shadow_traffic_gate import _evaluate

        ok, _summary = _evaluate(
            {"shadow_traffic_percent": 0.0, "regression_gate_enabled": True},
            min_shadow=10.0,
        )
        self.assertFalse(ok)


class WeeklyClosedLoopScriptTests(unittest.TestCase):
    def test_script_exists_and_references_steps(self) -> None:
        script = (ROOT / "scripts" / "weekly_closed_loop.sh").read_text(encoding="utf-8")
        self.assertIn("Termit weekly closed loop", script)
        self.assertIn("shadow_traffic_gate.py", script)
        self.assertIn("weekly_eval.sh", script)
        self.assertIn("eval_orchestration_spike.py", script)

    def test_full_cycle_script_wires_normalize_and_loops(self) -> None:
        script = (ROOT / "scripts" / "weekly_full_cycle.sh").read_text(encoding="utf-8")
        self.assertIn("normalize_training_signals.py", script)
        self.assertIn("training_loop_full.sh", script)
        self.assertIn("weekly_closed_loop.sh", script)

    def test_weekly_eval_uses_ci_capability_tier_by_default(self) -> None:
        script = (ROOT / "scripts" / "weekly_eval.sh").read_text(encoding="utf-8")
        self.assertIn('TERMIT_CAP_GATE_TIER="${TERMIT_CAP_GATE_TIER:-ci}"', script)

    def test_local_orchestration_gate_script_exists(self) -> None:
        script = (ROOT / "scripts" / "run_local_orchestration_gate.sh").read_text(encoding="utf-8")
        self.assertIn("enable_orchestration_tool_loop.sh", script)
        self.assertIn("eval_orchestration_gate.py", script)
        self.assertIn('TERMIT_ORCH_GATE_TIER="${TERMIT_ORCH_GATE_TIER:-local}"', script)

    def test_full_cycle_captures_kpi_baseline(self) -> None:
        script = (ROOT / "scripts" / "weekly_full_cycle.sh").read_text(encoding="utf-8")
        self.assertIn("capture_eval_kpi_baseline.sh", script)

    def test_full_cycle_skips_cursor_kpi_when_auto_train(self) -> None:
        script = (ROOT / "scripts" / "weekly_full_cycle.sh").read_text(encoding="utf-8")
        self.assertIn("TERMIT_FINETUNE_AUTO_TRAIN", script)
        self.assertIn("model KPI baseline in training_loop_full", script)

    def test_strict_live_gate_script_has_retry_loop(self) -> None:
        script = (ROOT / "scripts" / "run_strict_live_orchestration_gate.sh").read_text(encoding="utf-8")
        self.assertIn("TERMIT_ORCH_STRICT_LIVE_RETRIES", script)
        self.assertIn("run_live_orchestration_gate.sh", script)

    def test_training_loop_week2_wires_auto_train(self) -> None:
        script = (ROOT / "scripts" / "training_loop_week2.sh").read_text(encoding="utf-8")
        self.assertIn("TERMIT_FINETUNE_AUTO_TRAIN", script)
        self.assertIn("get_finetune_service", script)
        self.assertIn("train_job", script)

    def test_weekly_closed_loop_can_run_learning_0423(self) -> None:
        script = (ROOT / "scripts" / "weekly_closed_loop.sh").read_text(encoding="utf-8")
        self.assertIn("TERMIT_WEEKLY_RUN_LEARNING_0423", script)
        self.assertIn("learning_loop_0423_ci.sh", script)

    def test_weekly_full_cycle_wires_learning_loop(self) -> None:
        script = (ROOT / "scripts" / "weekly_full_cycle.sh").read_text(encoding="utf-8")
        self.assertIn("learning_loop_0423_ci.sh", script)

    def test_do_all_verify_wires_learning_loop(self) -> None:
        script = (ROOT / "scripts" / "do_all_verify.sh").read_text(encoding="utf-8")
        self.assertIn("learning_loop_0423_ci.sh", script)
        self.assertIn("test_learning_loop_0423", script)

    def test_bash_syntax(self) -> None:
        for name in (
            "weekly_closed_loop.sh",
            "weekly_full_cycle.sh",
            "run_local_orchestration_gate.sh",
            "run_live_orchestration_gate.sh",
            "cloud_benchmark_cycle.sh",
            "dpo_gpu_train.sh",
            "capability_baseline_refresh.sh",
            "do_all_verify.sh",
            "do_all_verify_ci.sh",
            "do_all_verify_full.sh",
            "do_all_dpo_contract.sh",
            "bootstrap_ollama_ci.sh",
            "nightly_macos_live_orchestration.sh",
            "capture_eval_kpi_baseline.sh",
            "run_strict_live_orchestration_gate.sh",
            "learning_loop_0423.sh",
            "learning_loop_0423_ci.sh",
        ):
            proc = subprocess.run(
                ["bash", "-n", str(ROOT / "scripts" / name)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, f"{name}: {proc.stderr}")


class OrchestrationToolLoopGateTests(unittest.TestCase):
    def test_gate_requires_tool_loop_steps_when_configured(self) -> None:
        report = {
            "total": 2,
            "pass_rate": 1.0,
            "metrics_after": {"coder_retry_success_rate": 1.0},
            "delta": {"orchestration_tool_steps_total": 0},
        }
        proc = subprocess.run(
            ["python3", "scripts/eval_orchestration_gate.py"],
            input=json.dumps(report),
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={
                **dict(__import__("os").environ),
                "TERMIT_ORCH_MIN_PASS_RATE": "0.0",
                "TERMIT_ORCH_MIN_RETRY_SUCCESS_RATE": "0.0",
                "TERMIT_ORCH_MIN_TOTAL": "1",
                "TERMIT_ORCH_MIN_TOOL_LOOP_STEPS": "1",
            },
            check=False,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("tool_loop_steps_delta", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
