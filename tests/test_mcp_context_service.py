from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import AgentProfileResponse, AgentRunRequest, TaskType
from app.services.agent_tool_schema import build_openai_tools
from app.services.mcp_context_service import McpContextService
from app.services.mcp_registry_service import McpRegistryService

_MCP_MOCK_WITH_READ = r"""
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
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {"tools": [{"name": "ping", "description": "demo", "inputSchema": {"type": "object"}}]}})
    elif method == "resources/list":
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {"resources": [{"uri": "demo://resource", "name": "demo", "description": "demo resource", "mimeType": "text/plain"}]}})
    elif method == "resources/read":
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {"contents": [{"uri": "demo://resource", "text": "demo resource body"}]}})
    elif method == "prompts/list":
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {"prompts": [{"name": "plan_starter", "description": "Planning template", "arguments": []}]}})
    elif method == "prompts/get":
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {"description": "Planning template", "messages": [{"role": "user", "content": {"type": "text", "text": "Start planning with MCP context"}}]}})
    elif method == "ping":
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {}})
"""


class McpContextServiceTests(unittest.TestCase):
    def test_build_context_lines_injects_resource_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script_path = Path(tmp) / "mock_mcp.py"
            script_path.write_text(_MCP_MOCK_WITH_READ, encoding="utf-8")
            registry_path = Path(tmp) / "registry.json"
            registry = McpRegistryService(str(registry_path))
            self.addCleanup(registry.close_sessions)
            server = registry.upsert_server(
                name="mock",
                command=sys.executable,
                args=[str(script_path)],
                allowed_tools=["ping"],
            )
            profile = AgentProfileResponse(
                agent_id="a1",
                name="Demo",
                task_type=TaskType.coding,
                system_prompt="demo",
                enabled_tools=["mcp_invoke"],
                allowed_mcp_servers=[server.server_id],
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            lines = McpContextService(registry).build_context_lines(profile)
            joined = "\n".join(lines)
            self.assertIn("[MCP context]", joined)
            self.assertIn("demo://resource", joined)
            self.assertIn("demo resource body", joined)

    def test_build_plan_prompt_lines_injects_prompt_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script_path = Path(tmp) / "mock_mcp.py"
            script_path.write_text(_MCP_MOCK_WITH_READ, encoding="utf-8")
            registry_path = Path(tmp) / "registry.json"
            registry = McpRegistryService(str(registry_path))
            self.addCleanup(registry.close_sessions)
            server = registry.upsert_server(
                name="mock",
                command=sys.executable,
                args=[str(script_path)],
                allowed_tools=["ping"],
            )
            profile = AgentProfileResponse(
                agent_id="a1",
                name="Demo",
                task_type=TaskType.coding,
                system_prompt="demo",
                enabled_tools=["mcp_get_prompt"],
                allowed_mcp_servers=[server.server_id],
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            lines = McpContextService(registry).build_plan_prompt_lines(profile)
            joined = "\n".join(lines)
            self.assertIn("[MCP plan prompts]", joined)
            self.assertIn("plan_starter", joined)
            self.assertIn("Start planning with MCP context", joined)

    def test_build_openai_tools_adds_mcp_companion_tools(self) -> None:
        tools = build_openai_tools(["read_file", "mcp_invoke"])
        names = [item["function"]["name"] for item in tools]
        self.assertIn("mcp_read_resource", names)
        self.assertIn("mcp_get_prompt", names)

    def test_mcp_context_inject_request_flag(self) -> None:
        default_payload = AgentRunRequest(input="demo")
        self.assertIsNone(default_payload.mcp_context_inject)
        disabled = AgentRunRequest(input="demo", mcp_context_inject=False)
        self.assertFalse(disabled.mcp_context_inject)


if __name__ == "__main__":
    unittest.main()
