from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app


class PlanBuildApiTests(unittest.TestCase):
    def test_build_from_plan_enqueues_agent_run(self) -> None:
        client = TestClient(app)
        response = client.post(
            "/api/orchestration/build-from-plan",
            json={
                "plan_text": "1. Read README.md\n2. Add onboarding note",
                "objective": "Improve onboarding docs",
                "verify_after_patch": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["run_id"].startswith("arun_"))
        self.assertTrue(body["agent_id"])
        self.assertEqual(body["state"], "queued")
        self.assertGreaterEqual(body["queued_position"], 1)
        self.assertIn("Implement the approved plan", body["input_preview"])

    def test_build_from_plan_metrics_counter(self) -> None:
        client = TestClient(app)
        before = client.get("/api/orchestration/metrics").json()
        client.post(
            "/api/orchestration/build-from-plan",
            json={"plan_text": "- Step A\n- Step B"},
        )
        after = client.get("/api/orchestration/metrics").json()
        self.assertIn("plan_build_enqueued_total", after)
        self.assertGreaterEqual(
            after["plan_build_enqueued_total"],
            before.get("plan_build_enqueued_total", 0) + 1,
        )


if __name__ == "__main__":
    unittest.main()
