import time
import unittest

from fastapi.testclient import TestClient

from app.main import app


class PlatformE2ETests(unittest.TestCase):
    def test_health_smoke_chain(self) -> None:
        client = TestClient(app)
        for path in (
            "/health",
            "/healthz",
            "/api/metrics/thresholds",
            "/api/ops/readiness",
            "/api/ops/agent-runs/metrics",
        ):
            response = client.get(path)
            self.assertEqual(response.status_code, 200, msg=path)

        metrics = client.get("/api/ops/agent-runs/metrics").json()
        self.assertIn("tool_loop_runs", metrics)
        self.assertIn("tool_loop_tool_success_rate", metrics)

    def test_chat_apply_patch_agent_run_flow(self) -> None:
        client = TestClient(app)

        chat_resp = client.post(
            "/api/chat",
            json={"message": "ping", "task_type": "general", "use_memory": False},
        )
        self.assertIn(chat_resp.status_code, {200, 400})

        patch_resp = client.post(
            "/api/tools/apply_patch",
            json={
                "path": "data/eval_fixtures/patch_sample.txt",
                "hunks": [{"old_text": "hello", "new_text": "hello"}],
                "dry_run": True,
                "confirmed": False,
            },
        )
        self.assertEqual(patch_resp.status_code, 200)
        self.assertFalse(patch_resp.json()["applied"])

        create_resp = client.post(
            "/api/agents",
            json={
                "name": "Platform E2E Agent",
                "description": "platform smoke",
                "system_prompt": "You are a test agent.",
                "task_type": "general",
                "allow_online": True,
                "enabled_tools": ["web_automation"],
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        agent_id = create_resp.json()["agent_id"]

        run_resp = client.post(
            f"/api/agents/{agent_id}/runs",
            json={
                "input": "collect web evidence",
                "online_url": "https://example.com",
                "online_objective": "Collect page evidence",
            },
        )
        self.assertEqual(run_resp.status_code, 200)
        run_id = run_resp.json()["run_id"]

        state = "queued"
        for _ in range(40):
            status_resp = client.get(f"/api/agents/runs/{run_id}")
            self.assertEqual(status_resp.status_code, 200)
            state = status_resp.json()["state"]
            if state in {"completed", "failed"}:
                break
            time.sleep(0.05)

        self.assertEqual(state, "completed")

        stream_resp = client.get(f"/api/agents/runs/{run_id}/stream?poll_ms=50&timeout_seconds=10")
        self.assertEqual(stream_resp.status_code, 200)
        self.assertIn("event: done", stream_resp.text)


if __name__ == "__main__":
    unittest.main()
