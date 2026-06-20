"""Тесты PlanStatusService и GET /api/ops/plan-status."""

from __future__ import annotations

import json
import os
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

    def test_relax_env_warnings_filters_gpu_and_cloud(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data" / "eval_kpi_last.json").write_text(
                json.dumps({"kpi_passed": True, "delta": 0.06}),
                encoding="utf-8",
            )
            service = PlanStatusService(
                project_root=root,
                kpi_gate_service=MagicMock(
                    evaluate_gates=MagicMock(return_value={"overall_passed": True, "gates": []})
                ),
                beta_service=MagicMock(
                    build_metrics=MagicMock(
                        return_value={"cohort_size_d30": 10, "d30_retention_rate": 0.4}
                    )
                ),
                automation_service=MagicMock(
                    snapshot=MagicMock(return_value={"automatic_mode_enabled": True})
                ),
                gpu_probe=lambda: {"gpu_available": False},
                cloud_probe=lambda: {"ready": False, "reason": "missing_api_key"},
            )
            with patch.dict(os.environ, {"TERMIT_PLAN_STATUS_RELAX_ENV_WARNINGS": "true"}, clear=False):
                payload = service.collect(from_running_api=True)
        self.assertTrue(payload["relax_env_warnings_enabled"])
        self.assertEqual(len(payload["warnings"]), 0)
        self.assertGreaterEqual(len(payload["relaxed_env_warnings"]), 2)
        self.assertTrue(payload["overall_ok"])

    def test_beta_cohort_uses_cohort_size_d30(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data" / "eval_kpi_last.json").write_text(
                json.dumps({"kpi_passed": True}),
                encoding="utf-8",
            )
            service = PlanStatusService(
                project_root=root,
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

    def test_reload_dev_metrics_seed_endpoint(self) -> None:
        import os
        import tempfile

        from app.state import _build_telemetry_store, reload_dev_telemetry_seed

        with tempfile.TemporaryDirectory() as tmp:
            desktop = Path(tmp) / "desktop"
            desktop.mkdir()
            seed_payload = {
                "dev_only": True,
                "chat_latencies_ms": [750] * 55,
                "chat_requests_total": 55,
                "chat_success_total": 55,
            }
            (desktop / "dev_chat_metrics_seed.json").write_text(
                json.dumps(seed_payload), encoding="utf-8"
            )
            with patch.dict(os.environ, {"TERMIT_DESKTOP_STATE_DIR": str(desktop)}, clear=False):
                _build_telemetry_store.cache_clear()
                direct = reload_dev_telemetry_seed()
                self.assertTrue(direct.get("reloaded"))
                response = self.client.post("/api/ops/reload-dev-metrics-seed")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body.get("reloaded"))
            self.assertGreaterEqual(int(body.get("chat_requests_total", 0)), 55)


if __name__ == "__main__":
    unittest.main()
