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


if __name__ == "__main__":
    unittest.main()
