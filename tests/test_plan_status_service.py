"""Тесты PlanStatusService и GET /api/ops/plan-status."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.plan_status_service import PlanStatusService
from app.main import app
from fastapi.testclient import TestClient


class PlanStatusServiceTests(unittest.TestCase):
    def test_collect_from_running_api_no_api_down_blocker(self) -> None:
        service = PlanStatusService(
            kpi_gate_service=MagicMock(
                evaluate_gates=MagicMock(return_value={"overall_passed": True, "gates": []})
            ),
            beta_service=MagicMock(
                build_metrics=MagicMock(return_value={"cohort_size_d30": 10, "d30_retention_rate": 0.4})
            ),
            automation_service=MagicMock(
                snapshot=MagicMock(return_value={"automatic_mode_enabled": True})
            ),
            gpu_probe=lambda: {"gpu_available": False},
            cloud_probe=lambda: {"ready": False, "reason": "missing_api_key"},
        )
        payload = service.collect(from_running_api=True)
        self.assertTrue(payload["infra_ok"])
        self.assertFalse(any(item["id"] == "api_down" for item in payload["blockers"]))

    def test_beta_cohort_uses_cohort_size_d30(self) -> None:
        service = PlanStatusService(
            kpi_gate_service=MagicMock(evaluate_gates=MagicMock(return_value={})),
            beta_service=MagicMock(
                build_metrics=MagicMock(return_value={"cohort_size_d30": 2})
            ),
            automation_service=MagicMock(snapshot=MagicMock(return_value={})),
            gpu_probe=lambda: {"gpu_available": True},
            cloud_probe=lambda: {"ready": True},
        )
        payload = service.collect(from_running_api=True)
        self.assertTrue(any(item["id"] == "beta_cohort" for item in payload["warnings"]))


    def test_persist_snapshot_on_api_collect(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            service = PlanStatusService(
                project_root=root,
                kpi_gate_service=MagicMock(evaluate_gates=MagicMock(return_value={})),
                beta_service=MagicMock(build_metrics=MagicMock(return_value={"cohort_size_d30": 10})),
                automation_service=MagicMock(snapshot=MagicMock(return_value={"automatic_mode_enabled": True})),
                gpu_probe=lambda: {"gpu_available": True},
                cloud_probe=lambda: {"ready": True},
            )
            service.collect(from_running_api=True)
            snapshot_path = root / "data" / "plan_status_last.json"
            self.assertTrue(snapshot_path.is_file())
            payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["phase"], "5_production_kpi")


class PlanStatusApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_plan_status_endpoint(self) -> None:
        sample = {
            "phase": "5_production_kpi",
            "plan_code_complete": True,
            "infra_ok": True,
            "overall_ok": False,
            "automatic_mode_enabled": True,
            "gpu": {"gpu_available": False},
            "cloud_benchmark": {"ready": False},
            "finetune_eval_kpi": None,
            "desktop_kpi_gates": {"overall_passed": False},
            "beta_metrics": {"cohort_size_d30": 0},
            "d30_retention": None,
            "blockers": [],
            "warnings": [{"id": "no_gpu", "message": "test"}],
            "blocker_count": 0,
            "warning_count": 1,
        }
        with patch(
            "app.services.plan_status_service.build_plan_status_service",
            return_value=MagicMock(collect=MagicMock(return_value=sample)),
        ):
            response = self.client.get("/api/ops/plan-status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["phase"], "5_production_kpi")
        self.assertTrue(body["infra_ok"])


if __name__ == "__main__":
    unittest.main()
