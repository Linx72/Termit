from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import AgentProfileResponse, AgentRunRequest, TaskType
from app.services.agent_service import AgentService, _ASK_BLOCKED_TOOLS
from app.services.cursor_rules_importer import CursorRulesImporter
from app.services.mcp_registry_service import McpRegistryService
from app.services.mcp_stdio_client import McpStdioSession


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
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {"tools": [{"name": "ping", "description": "demo", "inputSchema": {"type": "object"}}]}})
    elif method == "tools/call":
        write_msg({"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": "pong"}]}})
"""


class P1PlatformTests(unittest.TestCase):
    def test_cursor_rules_importer_reads_mdc_and_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rules_dir = root / ".cursor" / "rules"
            rules_dir.mkdir(parents=True)
            (rules_dir / "demo.mdc").write_text(
                "---\nalwaysApply: true\ndescription: Demo rule\n---\n\nAlways reply in tests.\n",
                encoding="utf-8",
            )
            (root / "AGENTS.md").write_text("# Agents\nUse minimal diff.\n", encoding="utf-8")
            importer = CursorRulesImporter()
            block = importer.build_prompt_block(root, include_all=True)
            self.assertIn("Always reply in tests.", block)
            self.assertIn("Use minimal diff.", block)

    def test_ask_mode_blocks_write_tools(self) -> None:
        profile = AgentProfileResponse(
            agent_id="a1",
            name="Demo",
            task_type=TaskType.coding,
            system_prompt="demo",
            enabled_tools=[
                "read_file",
                "apply_patch",
                "execute_command",
                "mcp_invoke",
            ],
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        payload = AgentRunRequest(input="explain auth", run_mode="ask")
        service = object.__new__(AgentService)
        ask_profile, _ = service._apply_run_mode(profile, payload)
        self.assertNotIn("apply_patch", ask_profile.enabled_tools)
        self.assertNotIn("execute_command", ask_profile.enabled_tools)
        self.assertIn("read_file", ask_profile.enabled_tools)
        self.assertTrue(_ASK_BLOCKED_TOOLS)

    def test_mcp_stdio_session_initialize_and_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script_path = Path(tmp) / "mock_mcp.py"
            script_path.write_text(_MCP_MOCK_SERVER, encoding="utf-8")
            session = McpStdioSession(command="python3", args=[str(script_path)])
            try:
                tools = session.list_tools()
                self.assertEqual([item.name for item in tools], ["ping"])
                result = session.call_tool("ping", {"x": 1})
                self.assertIn("content", result)
            finally:
                session.close()

    def test_mcp_registry_session_invoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            script_path = Path(tmp) / "mock_mcp.py"
            script_path.write_text(_MCP_MOCK_SERVER, encoding="utf-8")
            registry_path = Path(tmp) / "registry.json"
            registry = McpRegistryService(str(registry_path))
            self.addCleanup(registry.close_sessions)
            server = registry.upsert_server(
                name="mock",
                command="python3",
                args=[str(script_path)],
                allowed_tools=["ping"],
            )
            payload = registry.invoke_tool(server.server_id, "ping", {"x": 1})
            self.assertIn("stdio_session", payload)
            tools = registry.list_tools(server.server_id)
            self.assertEqual(tools[0].name, "ping")


if __name__ == "__main__":
    unittest.main()
