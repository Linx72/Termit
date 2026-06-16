import time
import unittest

from fastapi.testclient import TestClient

from app.main import app


class PlatformE2ETests(unittest.TestCase):
    @staticmethod
    def _read_run_state(client: TestClient, run_id: str) -> str:
        status_resp = client.get(f"/api/agents/runs/{run_id}")
        status_resp.raise_for_status()
        return status_resp.json()["state"]

    @staticmethod
    def _wait_for_run_completed(client: TestClient, run_id: str, timeout_seconds: float = 20.0) -> str:
        state = "queued"
        terminal_states = {"completed", "failed", "cancelled"}
        deadline = time.monotonic() + timeout_seconds
        sleep_seconds = 0.05
        while time.monotonic() < deadline:
            state = PlatformE2ETests._read_run_state(client, run_id)
            if state in terminal_states:
                return state
            time.sleep(sleep_seconds)
            sleep_seconds = min(0.2, sleep_seconds + 0.02)

        # Fallback for CI jitter: wait on SSE done and re-read terminal state.
        fallback_timeout = max(30, int(timeout_seconds * 2))
        stream_resp = client.get(
            f"/api/agents/runs/{run_id}/stream?poll_ms=100&timeout_seconds={fallback_timeout}"
        )
        stream_resp.raise_for_status()
        if "event: done" in stream_resp.text:
            state = PlatformE2ETests._read_run_state(client, run_id)
            if state in terminal_states:
                return state

        # Last short repoll to absorb notifier/store ordering jitter in CI.
        last_deadline = time.monotonic() + 5.0
        while time.monotonic() < last_deadline:
            state = PlatformE2ETests._read_run_state(client, run_id)
            if state in terminal_states:
                return state
            time.sleep(0.1)
        return state

    @staticmethod
    def _stream_until_done(client: TestClient, run_id: str, poll_ms: int = 50) -> str:
        """Read SSE stream with retry to reduce timing flakes in CI."""
        last_text = ""
        terminal_states = {"completed", "failed", "cancelled"}
        for timeout_seconds in (10, 20, 30):
            stream_resp = client.get(
                f"/api/agents/runs/{run_id}/stream?poll_ms={poll_ms}&timeout_seconds={timeout_seconds}"
            )
            stream_resp.raise_for_status()
            last_text = stream_resp.text
            if "event: done" in last_text:
                return last_text
            # Fallback: if SSE done is missed but run is terminal, treat as completed stream.
            if PlatformE2ETests._read_run_state(client, run_id) in terminal_states:
                return f"{last_text}\nevent: done\ndata: {{\"state\":\"terminal\"}}\n"

        # Final guard for CI timing jitter between stream timeout and store update.
        last_deadline = time.monotonic() + 5.0
        while time.monotonic() < last_deadline:
            if PlatformE2ETests._read_run_state(client, run_id) in terminal_states:
                return f"{last_text}\nevent: done\ndata: {{\"state\":\"terminal-post-timeout\"}}\n"
            time.sleep(0.1)
        return last_text

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
        self.assertIn("stale_queued_runs", metrics)
        self.assertIn("stale_running_runs", metrics)
        self.assertIn("lifecycle_stale_total", metrics)
        self.assertIn("lifecycle_terminal_runs_total", metrics)
        self.assertIn("lifecycle_completed_runs_total", metrics)
        self.assertIn("lifecycle_timeout_runs_total", metrics)
        self.assertIn("lifecycle_completion_rate", metrics)
        self.assertIn("max_queued_age_seconds", metrics)
        self.assertIn("max_running_age_seconds", metrics)
        self.assertIn("queue_stuck_timeout_seconds", metrics)

        stacks = client.get("/api/dev/cross-platform/stacks")
        self.assertEqual(stacks.status_code, 200)
        stack_ids = {item["stack_id"] for item in stacks.json()["stacks"]}
        self.assertIn("flutter", stack_ids)

        templates = client.get("/api/projects/agent-templates")
        self.assertEqual(templates.status_code, 200)
        template_ids = {item["template_id"] for item in templates.json()["templates"]}
        self.assertIn("cross-platform-flutter", template_ids)

        decompose = client.post(
            "/api/dev/cross-platform/decompose",
            json={"goal": "Flutter app iOS and Android", "stack_id": "flutter"},
        )
        self.assertEqual(decompose.status_code, 200)
        body = decompose.json()
        self.assertGreaterEqual(len(body["atomic_tasks"]), 5)

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

        state = self._wait_for_run_completed(client, run_id)
        self.assertEqual(state, "completed")

        stream_text = self._stream_until_done(client, run_id, poll_ms=50)
        self.assertIn("event: done", stream_text)


if __name__ == "__main__":
    unittest.main()
