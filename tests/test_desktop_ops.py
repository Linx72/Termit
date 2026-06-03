from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.agent_policy_preset_service import AgentPolicyPresetService
from app.services.desktop_accelerator_service import DesktopAcceleratorService
from app.services.desktop_kpi_gate_service import DesktopKpiGateService


class DesktopOpsTests(unittest.TestCase):
    def test_policy_preset_service_loads_presets(self) -> None:
        root = Path(__file__).resolve().parents[1]
        service = AgentPolicyPresetService(str(root / "data" / "desktop_policy_presets.json"))
        presets = service.list_presets()
        ids = {item.preset_id for item in presets}
        self.assertIn("solo", ids)
        self.assertIn("team", ids)
        self.assertIn("strict", ids)

    def test_kpi_gate_service_evaluates(self) -> None:
        root = Path(__file__).resolve().parents[1]
        service = DesktopKpiGateService(
            str(root / "data" / "desktop_north_star.json"),
            eval_dashboard_provider=lambda: {"pass_rate": 0.8},
            agent_metrics_provider=lambda: {
                "tool_loop_completion_rate": 0.85,
                "tool_loop_tool_success_rate": 0.9,
            },
        )
        payload = service.evaluate_gates()
        self.assertTrue(payload["overall_passed"])
        self.assertGreaterEqual(int(payload["passed_count"]), 1)

    def test_accelerator_share_and_heavy_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = DesktopAcceleratorService(
                tmp,
                run_lookup=lambda run_id: {"run_id": run_id, "state": "completed"},
                eval_suite_runner=lambda category, limit: {
                    "total": 2,
                    "passed": 2,
                    "pass_rate": 1.0,
                    "category_filter": category,
                },
            )
            shared = service.share_run(run_id="arun_test123", team="core", note="demo")
            self.assertEqual(shared["run_id"], "arun_test123")
            listed = service.list_shared_runs(team="core")
            self.assertEqual(len(listed), 1)

            job = service.enqueue_heavy_job(job_type="eval_suite", payload={"limit": 1})
            self.assertEqual(job["state"], "queued")

    def test_desktop_api_routes(self) -> None:
        client = TestClient(app)
        journeys = client.get("/api/desktop/journeys")
        self.assertEqual(journeys.status_code, 200)
        body = journeys.json()
        self.assertGreaterEqual(len(body["journeys"]), 3)
        self.assertIn("kpi_targets", body)

        presets = client.get("/api/desktop/policy-presets")
        self.assertEqual(presets.status_code, 200)
        self.assertTrue(any(item["preset_id"] == "solo" for item in presets.json()))

        gates = client.get("/api/desktop/kpi-gates")
        self.assertEqual(gates.status_code, 200)
        self.assertIn("gates", gates.json())

        shared = client.post(
            "/api/desktop/shared-runs",
            json={"run_id": "arun_demo001", "team": "default", "note": "test"},
        )
        self.assertEqual(shared.status_code, 200)
        self.assertEqual(shared.json()["run_id"], "arun_demo001")

        heavy = client.post(
            "/api/desktop/heavy-jobs",
            json={"job_type": "refactor_batch", "payload": {"paths": ["app/main.py"]}},
        )
        self.assertEqual(heavy.status_code, 200)
        self.assertEqual(heavy.json()["job_type"], "refactor_batch")


if __name__ == "__main__":
    unittest.main()
