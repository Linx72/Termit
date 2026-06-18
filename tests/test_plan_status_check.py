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

        def fake_curl(url: str, api_key: str = "") -> dict | None:
            if url.endswith("/health"):
                return {"status": "ok"}
            if url.endswith("/api/ops/plan-status"):
                return None
            return None

        with patch("scripts.plan_status_check._curl_json", side_effect=fake_curl), patch(
            "app.services.plan_status_service.build_plan_status_service"
        ) as build_mock:
            build_mock.return_value.collect.return_value = {
                "phase": "5_production_kpi",
                "plan_code_complete": True,
                "infra_ok": True,
                "warnings": [],
                "blockers": [],
                "blocker_count": 0,
                "warning_count": 0,
            }
            payload = collect_plan_status()
        self.assertEqual(payload["phase"], "5_production_kpi")
        self.assertTrue(payload["plan_code_complete"])
        build_mock.return_value.collect.assert_called_once_with(external_api_ok=True)

    def test_collect_prefers_api_plan_status(self) -> None:
        from scripts.plan_status_check import collect_plan_status

        plan_payload = {"phase": "5_production_kpi", "infra_ok": True, "from_api": True}

        def fake_curl(url: str, api_key: str = "") -> dict | None:
            if url.endswith("/health"):
                return {"status": "ok"}
            if url.endswith("/api/ops/plan-status"):
                return plan_payload
            return None

        with patch("scripts.plan_status_check._curl_json", side_effect=fake_curl):
            payload = collect_plan_status()
        self.assertTrue(payload.get("from_api"))

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
