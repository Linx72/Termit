from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app


class OrchestrationApiTests(unittest.TestCase):
    def test_orchestration_metrics_endpoint_available(self) -> None:
        client = TestClient(app)
        response = client.get("/api/orchestration/metrics")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("orchestration_runs_total", body)
        self.assertIn("avg_coder_attempts", body)
        self.assertIn("coder_retry_success_rate", body)
        self.assertIn("openhands_contract_runs_total", body)
        self.assertIn("openhands_contract_actions_total", body)
        self.assertIn("orchestration_tool_loop_runs_total", body)
        self.assertIn("orchestration_tool_steps_total", body)
        self.assertIn("plan_build_enqueued_total", body)

    def test_orchestration_config_endpoint(self) -> None:
        client = TestClient(app)
        response = client.get("/api/orchestration/config")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("tool_loop_execution_enabled", body)
        self.assertIn("gate_tier", body)
        self.assertIn("require_tool_loop", body)
        self.assertIn("eval_fixture_coder_enabled", body)
        self.assertIn("tool_loop_fallback_enabled", body)


if __name__ == "__main__":
    unittest.main()
