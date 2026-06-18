"""Тесты plan_status_check.py."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class PlanStatusCheckTests(unittest.TestCase):
    def test_collect_plan_status_structure(self) -> None:
        from scripts.plan_status_check import collect_plan_status

        with patch("scripts.plan_status_check._curl_json", return_value={"status": "ok"}), patch(
            "scripts.plan_status_check._run_probe",
            side_effect=[
                {"gpu_available": False, "backend": "none", "devices": []},
                {"ready": False, "reason": "missing_api_key"},
            ],
        ):
            payload = collect_plan_status()
        self.assertEqual(payload["phase"], "5_production_kpi")
        self.assertTrue(payload["plan_code_complete"])
        self.assertIn("warnings", payload)

    def test_script_runs(self) -> None:
        python_bin = ROOT / ".venv/bin/python"
        if not python_bin.exists():
            python_bin = Path("python3")
        proc = subprocess.run(
            [str(python_bin), str(ROOT / "scripts/plan_status_check.py"), "--summary-only"],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Статус плана", proc.stdout)

    def test_do_all_plan_bash_syntax(self) -> None:
        proc = subprocess.run(
            ["bash", "-n", str(ROOT / "scripts/do_all_plan.sh")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
