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

        state = "queued"
        for _ in range(80):
            run_resp = client.get(f"/api/agents/runs/{run_id}")
            self.assertEqual(run_resp.status_code, 200)
            state = run_resp.json()["state"]
            if state in {"completed", "failed"}:
                break
            time.sleep(0.05)

        self.assertEqual(state, "completed")

        events_resp = client.get(f"/api/agents/runs/{run_id}/events")
        self.assertEqual(events_resp.status_code, 200)
        events = events_resp.json()
        self.assertGreaterEqual(len(events), 2)

        stream_resp = client.get(f"/api/agents/runs/{run_id}/stream?poll_ms=50&timeout_seconds=10")
        self.assertEqual(stream_resp.status_code, 200)
        self.assertIn("event: status", stream_resp.text)
        self.assertIn("event: done", stream_resp.text)

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


if __name__ == "__main__":
    unittest.main()
