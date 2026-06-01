from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app


class AgentDlqApiTests(unittest.TestCase):
    def test_list_dlq_runs_returns_200(self) -> None:
        client = TestClient(app)
        response = client.get("/api/agents/runs/dlq?limit=5")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("runs", body)
        self.assertIn("total", body)
        self.assertIsInstance(body["runs"], list)

    def test_replay_dlq_empty_is_ok(self) -> None:
        client = TestClient(app)
        response = client.post("/api/agents/runs/dlq/replay?limit=1")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("replayed", body)
        self.assertIn("count", body)


if __name__ == "__main__":
    unittest.main()
