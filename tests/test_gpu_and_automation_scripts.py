"""Tests for GPU probe and automation scripts."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CloudBenchmarkProbeTests(unittest.TestCase):
    def test_probe_reports_missing_key_by_default(self) -> None:
        python_bin = ROOT / ".venv" / "bin" / "python"
        if not python_bin.exists():
            python_bin = Path("python3")
        proc = subprocess.run(
            [str(python_bin), str(ROOT / "scripts" / "cloud_benchmark_probe.py")],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
            env={**dict(__import__("os").environ), "OPENAI_COMPAT_API_KEY": "", "OPENAI_API_KEY": ""},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload.get("ready"))

        self.assertIn("frontier_chain", payload)
        self.assertIn("DeepSeek-V4-Pro", str(payload.get("frontier_chain", "")))

    def test_dev_stub_reports_ready(self) -> None:
        python_bin = ROOT / ".venv" / "bin" / "python"
        if not python_bin.exists():
            python_bin = Path("python3")
        env = {
            **dict(__import__("os").environ),
            "TERMIT_CLOUD_BENCHMARK_DEV_READY": "true",
            "OPENAI_COMPAT_API_KEY": "",
            "OPENAI_API_KEY": "",
        }
        proc = subprocess.run(
            [str(python_bin), str(ROOT / "scripts" / "cloud_benchmark_probe.py")],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
            env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload.get("ready"))
        self.assertEqual(payload.get("reason"), "dev_stub")


class GpuProbeTests(unittest.TestCase):
    def test_probe_returns_structured_json(self) -> None:
        proc = subprocess.run(
            ["python3", str(ROOT / "scripts" / "gpu_probe.py")],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertIn("gpu_available", payload)
        self.assertIn("backend", payload)
        self.assertIn("devices", payload)


class AutomationScriptTests(unittest.TestCase):
    def test_bash_syntax_for_new_scripts(self) -> None:
        for name in (
            "install_automation_crontabs.sh",
            "bootstrap_ollama_ci.sh",
            "dpo_gpu_train.sh",
            "do_all_dpo_contract.sh",
            "do_all_verify_full.sh",
            "capability_baseline_refresh.sh",
            "cloud_benchmark_cycle.sh",
            "cloud_benchmark_probe.py",
            "nightly_macos_live_orchestration.sh",
            "capture_eval_kpi_baseline.sh",
            "run_strict_live_orchestration_gate.sh",
            "weekly_full_cycle.sh",
            "post_train_model_eval.py",
            "training_loop_week2.sh",
            "stage1_full_loop.sh",
            "do_all_plan.sh",
            "plan_status_check.py",
            "capture_plan_status_snapshot.sh",
            "seed_beta_cohort_dev.py",
            "seed_finetune_kpi_dev.py",
            "local_dev_kpi_seed.sh",
            "plan_status_dev_green.sh",
            "release_gate_local.sh",
            "reset_eval_patch_fixture.sh",
            "deploy_hosted_beta.sh",
            "gpu_probe.py",
            "learning_loop_0423.sh",
            "learning_loop_0423_report.py",
            "learning_loop_0423_ci.sh",
            "beta_staging_gate.sh",
            "start_colima_and_deploy_beta.sh",
            "release_gate_staging.sh",
            "pre_release_check.sh",
            "seed_hosted_product_kpi.sh",
            "beta_telemetry_report.py",
            "remote_gpu_dpo.sh",
            "upgrade_model_ladder_v4.sh",
            "phase0_v4_readiness.sh",
            "capability_benchmark_ci.sh",
            "v4_ladder_smoke.sh",
            "learning_loop_0423_ci.sh",
        ):
            if name.endswith(".sh"):
                proc = subprocess.run(
                    ["bash", "-n", str(ROOT / "scripts" / name)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, f"{name}: {proc.stderr}")

    def test_do_all_dpo_contract_exports_valid_dataset(self) -> None:
        python_bin = ROOT / ".venv" / "bin" / "python"
        if not python_bin.exists():
            python_bin = Path("python3")
        proc = subprocess.run(
            ["bash", str(ROOT / "scripts" / "do_all_dpo_contract.sh")],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
            env={
                **dict(__import__("os").environ),
                "TERMIT_DPO_EXPORT_NAME": "unittest-dpo-contract",
                "TERMIT_DPO_MIN_PAIRS": "1",
                "TERMIT_NORMALIZE_SIGNALS_BEFORE_DPO": "false",
            },
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("DPO contract gate passed", proc.stdout)


if __name__ == "__main__":
    unittest.main()
