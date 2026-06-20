"""Тесты beta activity API и beta telemetry report."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.main import app
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


def _load_beta_report_module():
    path = ROOT / "scripts" / "beta_telemetry_report.py"
    spec = importlib.util.spec_from_file_location("beta_telemetry_report", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BetaActivityApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_beta_activity_records_session(self) -> None:
        response = self.client.post(
            "/api/ops/beta/activity",
            json={"session_id": "test-beta-user-01", "source": "unittest"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["session_id"], "test-beta-user-01")
        self.assertIn("recorded_at", body)


class BetaTelemetryReportTests(unittest.TestCase):
    def test_evaluate_staging_ok_when_cohort_and_gates_pass(self) -> None:
        mod = _load_beta_report_module()
        summary = mod.evaluate_beta_staging(
            beta={
                "cohort_size_d30": 6,
                "d30_retention_rate": 0.5,
                "target_d30_retention": 0.35,
                "tracked_actors": 8,
            },
            gates={"overall_passed": True, "gates": []},
            min_cohort_d30=5,
        )
        self.assertTrue(summary["cohort_ok"])
        self.assertTrue(summary["staging_ok"])

    def test_evaluate_staging_fails_small_cohort(self) -> None:
        mod = _load_beta_report_module()
        summary = mod.evaluate_beta_staging(
            beta={"cohort_size_d30": 2, "tracked_actors": 2},
            gates={"overall_passed": True, "gates": []},
            min_cohort_d30=5,
        )
        self.assertFalse(summary["staging_ok"])

    def test_evaluate_staging_real_mode_without_product_gates(self) -> None:
        mod = _load_beta_report_module()
        summary = mod.evaluate_beta_staging(
            beta={"tracked_actors": 6, "active_users_7d": 4, "cohort_size_d30": 0},
            gates={"overall_passed": False, "gates": []},
            min_cohort_d30=5,
            gate_mode="real",
            min_tracked=5,
            min_active_7d=3,
            require_product_gates=False,
        )
        self.assertTrue(summary["staging_ok"])


class PlanStatusBetaMetaTests(unittest.TestCase):
    def test_beta_dev_seed_warning_instead_of_small_cohort(self) -> None:
        from app.services.plan_status_service import PlanStatusService

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data" / "beta_cohort_meta.json").write_text(
                json.dumps({"dev_only": True}),
                encoding="utf-8",
            )
            (root / "data" / "eval_kpi_last.json").write_text(
                json.dumps({"kpi_passed": True}),
                encoding="utf-8",
            )
            service = PlanStatusService(
                project_root=root,
                kpi_gate_service=MagicMock(
                    evaluate_gates=MagicMock(return_value={"overall_passed": True, "gates": []})
                ),
                beta_service=MagicMock(
                    build_metrics=MagicMock(return_value={"cohort_size_d30": 2})
                ),
                automation_service=MagicMock(snapshot=MagicMock(return_value={})),
                gpu_probe=lambda: {"gpu_available": True},
                cloud_probe=lambda: {"ready": True},
            )
            payload = service.collect(from_running_api=True)
        self.assertTrue(any(item["id"] == "beta_cohort_dev_seed" for item in payload["warnings"]))
        self.assertFalse(any(item["id"] == "beta_cohort" for item in payload["warnings"]))


if __name__ == "__main__":
    unittest.main()
