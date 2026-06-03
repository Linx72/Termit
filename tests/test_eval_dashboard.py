from __future__ import annotations

import unittest

from app.services.eval_service import EvalService


class EvalDashboardTests(unittest.TestCase):
    def test_build_dashboard_includes_kpi_fields(self) -> None:
        service = EvalService(scenarios_path="data/eval_scenarios.json")
        dashboard = service.build_dashboard(report_limit=3)
        self.assertIn("pass_rate", dashboard)
        self.assertIn("latency_p95_ms", dashboard)
        self.assertIn("estimated_cost_usd", dashboard)
        self.assertIn("scenario_count", dashboard)
        self.assertGreaterEqual(int(dashboard["scenario_count"]), 53)

    def test_eval_dashboard_api(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.routes.eval import router as eval_router
        from app.state import get_eval_service

        app = FastAPI()
        app.include_router(eval_router)
        app.dependency_overrides[get_eval_service] = lambda: EvalService(
            scenarios_path="data/eval_scenarios.json"
        )
        client = TestClient(app)
        response = client.get("/api/eval/dashboard?limit=3")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["scenario_count"], 53)


if __name__ == "__main__":
    unittest.main()
