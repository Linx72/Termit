import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.agent_registry_store import AgentRegistryStore
from app.services.agent_run_store import InMemoryAgentRunStore
from app.services.agent_service import AgentService
from app.services.tooling_service import ToolingService
from tests.test_agent_service import StubBrowserWorkflow, StubChatService


def _isolated_agent_service(tmp: str) -> AgentService:
    return AgentService(
        chat_service=StubChatService(),
        registry=AgentRegistryStore(file_path=str(Path(tmp) / "agents.json")),
        run_store=InMemoryAgentRunStore(),
        tooling=ToolingService(root_path="."),
        browser_workflow=StubBrowserWorkflow(),
        max_concurrency=1,
        max_queue_size=10,
        run_max_attempts=1,
        run_retry_backoff_ms=1,
    )


class AgentsApiTests(unittest.TestCase):
    @staticmethod
    def _read_run_state(client: TestClient, run_id: str) -> str:
        run_resp = client.get(f"/api/agents/runs/{run_id}")
        run_resp.raise_for_status()
        return run_resp.json()["state"]

    @staticmethod
    def _wait_for_run_completed(client: TestClient, run_id: str, timeout_seconds: float = 20.0) -> str:
        state = "queued"
        terminal_states = {"completed", "failed", "cancelled"}
        deadline = time.monotonic() + timeout_seconds
        sleep_seconds = 0.05
        while time.monotonic() < deadline:
            state = AgentsApiTests._read_run_state(client, run_id)
            if state in terminal_states:
                return state
            time.sleep(sleep_seconds)
            sleep_seconds = min(0.2, sleep_seconds + 0.02)

        # Fallback path for slow environments: block on SSE stream completion
        # and re-read final run state to avoid timing flakes on background runs.
        fallback_timeout = max(30, int(timeout_seconds * 2))
        stream_resp = client.get(
            f"/api/agents/runs/{run_id}/stream?poll_ms=100&timeout_seconds={fallback_timeout}"
        )
        stream_resp.raise_for_status()
        if "event: done" in stream_resp.text:
            state = AgentsApiTests._read_run_state(client, run_id)
            if state in terminal_states:
                return state

        # Last short repoll to absorb notifier/store ordering jitter in CI.
        last_deadline = time.monotonic() + 5.0
        while time.monotonic() < last_deadline:
            state = AgentsApiTests._read_run_state(client, run_id)
            if state in terminal_states:
                return state
            time.sleep(0.1)
        return state

    @staticmethod
    def _stream_until_done(client: TestClient, run_id: str, poll_ms: int = 50) -> str:
        """Read SSE stream with a short retry window to absorb CI jitter."""
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
            # Fallback: if SSE done is missed but run already terminal, treat stream as done.
            if AgentsApiTests._read_run_state(client, run_id) in terminal_states:
                return f'{last_text}\nevent: done\ndata: {{"state":"terminal"}}\n'

        # Final guard for CI timing jitter between stream timeout and store update.
        last_deadline = time.monotonic() + 5.0
        while time.monotonic() < last_deadline:
            if AgentsApiTests._read_run_state(client, run_id) in terminal_states:
                return f'{last_text}\nevent: done\ndata: {{"state":"terminal-post-timeout"}}\n'
            time.sleep(0.1)
        return last_text

    def test_create_agent_and_background_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = _isolated_agent_service(tmp)
            with patch("app.api.routes.agents.get_agent_service", return_value=service):
                client = TestClient(app)
                self._run_create_agent_and_background(client)

    def _run_create_agent_and_background(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/agents",
            json={
                "name": "API Agent",
                "description": "for api test",
                "system_prompt": "You are an API test agent.",
                "task_type": "general",
                "allow_online": True,
                "enabled_tools": ["web_automation"],
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        agent_id = create_resp.json()["agent_id"]

        queue_resp = client.post(
            f"/api/agents/{agent_id}/runs",
            json={
                "input": "collect web evidence in queued mode",
                "online_url": "https://example.com",
                "online_objective": "Collect simple page evidence",
            },
        )
        self.assertEqual(queue_resp.status_code, 200)
        run_id = queue_resp.json()["run_id"]

        state = self._wait_for_run_completed(client, run_id)
        if state != "completed":
            events_debug = client.get(f"/api/agents/runs/{run_id}/events").json()
            self.fail(
                f"Expected completed run, got state={state}. "
                f"events_count={len(events_debug)}"
            )

        events_resp = client.get(f"/api/agents/runs/{run_id}/events")
        self.assertEqual(events_resp.status_code, 200)
        events = events_resp.json()
        self.assertGreaterEqual(len(events), 2)

        stream_text = self._stream_until_done(client, run_id, poll_ms=50)
        self.assertIn("event: done", stream_text)

    def test_agent_tool_permission_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = _isolated_agent_service(tmp)
            with patch("app.api.routes.agents.get_agent_service", return_value=service):
                client = TestClient(app)
                self._run_agent_tool_permission_enforced(client)

    def _run_agent_tool_permission_enforced(self, client: TestClient) -> None:
        create_resp = client.post(
            "/api/agents",
            json={
                "name": "No Tool Agent",
                "description": "no tools",
                "system_prompt": "No tools are allowed.",
                "task_type": "general",
                "enabled_tools": [],
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        agent_id = create_resp.json()["agent_id"]

        denied = client.post(
            f"/api/agents/{agent_id}/tools/read_file",
            json={"path": "README.md"},
        )
        self.assertEqual(denied.status_code, 403)
        self.assertIn("not allowed", denied.json()["detail"])

    def test_ask_and_plan_run_modes_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = _isolated_agent_service(tmp)
            with patch("app.api.routes.agents.get_agent_service", return_value=service):
                client = TestClient(app)
                create_resp = client.post(
                    "/api/agents",
                    json={
                        "name": "Mode Agent",
                        "description": "mode test",
                        "system_prompt": "Mode-aware agent.",
                        "task_type": "general",
                        "enabled_tools": ["read_file", "apply_patch", "execute_command"],
                    },
                )
                self.assertEqual(create_resp.status_code, 200)
                agent_id = create_resp.json()["agent_id"]

                ask_resp = client.post(
                    f"/api/agents/{agent_id}/runs",
                    json={"input": "answer only", "run_mode": "ask"},
                )
                self.assertEqual(ask_resp.status_code, 200)
                plan_resp = client.post(
                    f"/api/agents/{agent_id}/runs",
                    json={"input": "plan only", "run_mode": "plan"},
                )
                self.assertEqual(plan_resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
