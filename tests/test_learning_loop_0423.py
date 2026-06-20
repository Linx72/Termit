"""Тесты learning loop 0.4.23 (report builder, scenario ids, plan status)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]


def _load_report_module():
    path = ROOT / "scripts" / "learning_loop_0423_report.py"
    spec = importlib.util.spec_from_file_location("learning_loop_0423_report", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LearningLoop0423ReportTests(unittest.TestCase):
    def test_default_post_dpo_scenario_ids_full(self) -> None:
        mod = _load_report_module()
        with unittest.mock.patch.dict(
            os.environ,
            {"TERMIT_EVAL_POST_DPO_FULL": "true"},
            clear=False,
        ):
            ids = mod.default_post_dpo_scenario_ids()
        self.assertIn("HE1", ids)
        self.assertIn("MBPP1", ids)
        self.assertIn("MB1", ids)

    def test_build_report_marks_real_train_on_gpu(self) -> None:
        mod = _load_report_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline.json"
            post = root / "post.json"
            kpi = root / "kpi.json"
            baseline.write_text(json.dumps({"pass_rate": 0.5}), encoding="utf-8")
            post.write_text(json.dumps({"pass_rate": 0.6}), encoding="utf-8")
            kpi.write_text(
                json.dumps({"kpi_passed": True, "delta": 0.1}),
                encoding="utf-8",
            )
            report = mod.build_learning_loop_report(
                gpu={"gpu_available": True, "backend": "nvidia-smi", "devices": ["T4"]},
                cloud={"ready": True, "reason": "ok"},
                dpo_train={"status": "completed", "detail": "Unsloth DPO training completed."},
                baseline_path=baseline,
                post_dpo_path=post,
                kpi_path=kpi,
                scenario_ids="MB1,HE1",
                model="ollama:termit-core-ft",
                cloud_benchmark_ran=True,
            )
        self.assertTrue(report["dpo_real_train"])
        self.assertTrue(report["kpi_passed"])
        self.assertEqual(report["baseline_pass_rate"], 0.5)
        self.assertEqual(report["post_dpo_pass_rate"], 0.6)

    def test_build_report_dry_run_without_gpu(self) -> None:
        mod = _load_report_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline.json"
            post = root / "post.json"
            kpi = root / "kpi.json"
            for path, rate in ((baseline, 0.4), (post, 0.42), (kpi, 0.02)):
                pass
            baseline.write_text(json.dumps({"pass_rate": 0.4}), encoding="utf-8")
            post.write_text(json.dumps({"pass_rate": 0.42}), encoding="utf-8")
            kpi.write_text(json.dumps({"kpi_passed": False, "delta": 0.02}), encoding="utf-8")
            report = mod.build_learning_loop_report(
                gpu={"gpu_available": False},
                cloud={"ready": False, "reason": "missing_api_key"},
                dpo_train={"status": "completed", "detail": "HF DPO dry-run"},
                baseline_path=baseline,
                post_dpo_path=post,
                kpi_path=kpi,
                scenario_ids="MB1,MB2,MB3",
                model="ollama:termit-core-ft",
                cloud_benchmark_ran=False,
            )
        self.assertFalse(report["dpo_real_train"])


class PlanStatusLearningLoopTests(unittest.TestCase):
    def test_dpo_dry_run_warning_when_artifact_without_real_train(self) -> None:
        from app.services.plan_status_service import PlanStatusService

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data" / "eval_kpi_last.json").write_text(
                json.dumps({"kpi_passed": False, "delta": 0.01}),
                encoding="utf-8",
            )
            (root / "data" / "learning_loop_0423_last.json").write_text(
                json.dumps({"dpo_real_train": False, "phase": "0.4.23"}),
                encoding="utf-8",
            )
            service = PlanStatusService(
                project_root=root,
                kpi_gate_service=MagicMock(evaluate_gates=MagicMock(return_value={"overall_passed": True})),
                beta_service=MagicMock(build_metrics=MagicMock(return_value={"cohort_size_d30": 10})),
                automation_service=MagicMock(snapshot=MagicMock(return_value={})),
                gpu_probe=lambda: {"gpu_available": False},
                cloud_probe=lambda: {"ready": True},
            )
            payload = service.collect(from_running_api=True)
        self.assertTrue(any(item["id"] == "dpo_dry_run" for item in payload["warnings"]))


    def test_kpi_not_measurable_without_real_dpo(self) -> None:
        mod = _load_report_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline = root / "baseline.json"
            post = root / "post.json"
            kpi = root / "kpi.json"
            baseline.write_text(json.dumps({"pass_rate": 1.0}), encoding="utf-8")
            post.write_text(json.dumps({"pass_rate": 1.0}), encoding="utf-8")
            kpi.write_text(json.dumps({"kpi_passed": False, "delta": 0.0}), encoding="utf-8")
            report = mod.build_learning_loop_report(
                gpu={"gpu_available": False},
                cloud={"ready": False},
                dpo_train={"status": "completed", "detail": "HF DPO dry-run"},
                baseline_path=baseline,
                post_dpo_path=post,
                kpi_path=kpi,
                scenario_ids="MB1,HE1",
                model="ollama:termit-core-ft",
                cloud_benchmark_ran=False,
            )
        self.assertFalse(report["kpi_measurable"])

    def test_plan_status_skips_kpi_warning_when_not_measurable(self) -> None:
        from app.services.plan_status_service import PlanStatusService

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data" / "eval_kpi_last.json").write_text(
                json.dumps({"kpi_passed": False, "delta": 0.0}),
                encoding="utf-8",
            )
            (root / "data" / "learning_loop_0423_last.json").write_text(
                json.dumps({"dpo_real_train": False, "kpi_measurable": False}),
                encoding="utf-8",
            )
            service = PlanStatusService(
                project_root=root,
                kpi_gate_service=MagicMock(evaluate_gates=MagicMock(return_value={"overall_passed": True})),
                beta_service=MagicMock(build_metrics=MagicMock(return_value={"cohort_size_d30": 10})),
                automation_service=MagicMock(snapshot=MagicMock(return_value={})),
                gpu_probe=lambda: {"gpu_available": False},
                cloud_probe=lambda: {"ready": True},
            )
            payload = service.collect(from_running_api=True)
        self.assertFalse(any(item["id"] == "finetune_kpi" for item in payload["warnings"]))


class LearningLoopScriptSyntaxTests(unittest.TestCase):
    def test_bash_syntax(self) -> None:
        for name in (
            "learning_loop_0423.sh",
            "learning_loop_0423_ci.sh",
            "remote_gpu_dpo.sh",
            "gpu_dpo_preflight.sh",
            "build_clients.sh",
            "beta_prod_gate.sh",
        ):
            proc = subprocess.run(
                ["bash", "-n", str(ROOT / "scripts" / name)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, f"{name}: {proc.stderr}")

    def test_gpu_dpo_preflight_fails_without_gpu(self) -> None:
        env = os.environ.copy()
        env.pop("TERMIT_REMOTE_GPU_SSH", None)
        proc = subprocess.run(
            [str(ROOT / "scripts" / "gpu_dpo_preflight.sh")],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            cwd=str(ROOT),
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("BLOCKER", proc.stderr)


if __name__ == "__main__":
    unittest.main()
