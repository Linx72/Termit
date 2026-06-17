from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.desktop_kpi_gate_service import DesktopKpiGateService
from app.services.mcp_registry_service import McpRegistryService


_MCP_MOCK_SERVER = r"""
import json, sys

def read_msg():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        line = line.decode("utf-8").strip()
        if line == "":
            break
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers["content-length"])
    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))

def write_msg(payload):
    data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()

while True:
    msg = read_msg()
    if msg is None:
        break
    method = msg.get("method")
    req_id = msg.get("id")
    if method == "initialize":
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {}}})
    elif method == "tools/list":
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {"tools": []}})
    elif method == "ping":
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {}})
    elif method == "resources/list":
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {"resources": []}})
    elif method == "prompts/list":
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {"prompts": []}})
"""


class McpFullJsonRpcApiTests(unittest.TestCase):
    def test_platform_mcp_ping_resources_prompts(self) -> None:
        from fastapi.testclient import TestClient

        from app.main import app
        from app.state import get_mcp_registry_service

        with tempfile.TemporaryDirectory() as tmp:
            script_path = Path(tmp) / "mock_mcp.py"
            script_path.write_text(_MCP_MOCK_SERVER, encoding="utf-8")
            registry_path = Path(tmp) / "registry.json"
            registry = McpRegistryService(str(registry_path))
            server = registry.upsert_server(
                name="mock-full",
                command="python3",
                args=[str(script_path)],
            )
            server_id = server.server_id

            app.dependency_overrides[get_mcp_registry_service] = lambda: registry
            try:
                client = TestClient(app)
                ping = client.get(f"/api/platform/mcp/servers/{server_id}/ping")
                self.assertEqual(ping.status_code, 200)
                self.assertTrue(ping.json()["ok"])

                resources = client.get(f"/api/platform/mcp/servers/{server_id}/resources")
                self.assertEqual(resources.status_code, 200)
                self.assertEqual(resources.json()["resources"], [])

                prompts = client.get(f"/api/platform/mcp/servers/{server_id}/prompts")
                self.assertEqual(prompts.status_code, 200)
                self.assertEqual(prompts.json()["prompts"], [])
            finally:
                app.dependency_overrides.clear()
                registry.close_sessions()


class OnboardingKpiGateTests(unittest.TestCase):
    def test_onboarding_conversion_gate_when_cohort_large_enough(self) -> None:
        service = DesktopKpiGateService(
            "data/desktop_north_star.json",
            eval_dashboard_provider=lambda: {"pass_rate": 0.9},
            agent_metrics_provider=lambda: {
                "tool_loop_completion_rate": 0.9,
                "tool_loop_tool_success_rate": 0.9,
            },
            onboarding_metrics_provider=lambda: {
                "total_assigned": 10,
                "overall_conversion_rate": 0.6,
            },
        )
        payload = service.evaluate_gates()
        gate_ids = [str(item["gate_id"]) for item in payload["gates"]]
        self.assertIn("onboarding_conversion", gate_ids)
        onboarding_gate = next(item for item in payload["gates"] if item["gate_id"] == "onboarding_conversion")
        self.assertTrue(onboarding_gate["passed"])


if __name__ == "__main__":
    unittest.main()
