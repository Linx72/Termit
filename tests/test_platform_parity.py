from __future__ import annotations

import json
import unittest

from app.services.agent_hook_service import AgentHookService, HookEvent
from app.services.guardrail_service import GuardrailService
from app.services.mcp_registry_service import McpRegistryService
from app.services.search_provider import StubSearchProvider
from app.services.skill_store import SkillStore
from app.services.trace_span_store import TraceSpanStore
from pathlib import Path
import tempfile


class PlatformParityTests(unittest.TestCase):
    def test_guardrail_blocks_secret_prompt(self) -> None:
        guard = GuardrailService()
        result = guard.check_prompt("api_key=supersecretvalue123456")
        self.assertFalse(result.allowed)

    def test_guardrail_blocks_secret_patch(self) -> None:
        guard = GuardrailService()
        result = guard.check_patch_content("password=supersecretvalue123456")
        self.assertFalse(result.allowed)
        self.assertIn("secrets", result.reason.lower())

    def test_skill_store_lists_bundled_skills(self) -> None:
        root = Path(__file__).resolve().parents[1] / "data" / "skills"
        store = SkillStore(str(root))
        skills = store.list_skills()
        ids = {item.skill_id for item in skills}
        self.assertIn("fix-ci", ids)
        self.assertIn("cross-platform-atomic", ids)
        block = store.build_prompt_block(["fix-ci"])
        self.assertIn("Fix CI", block)
        cp_block = store.build_prompt_block(["cross-platform-atomic"])
        self.assertIn("Cross-platform atomic", cp_block)
        self.assertIn("online-project", ids)
        self.assertIn("web-app", ids)
        self.assertIn("termit-desktop", ids)
        self.assertIn("agent-guided", ids)
        self.assertIn("agent-autopilot", ids)
        self.assertIn("termit-platform", ids)
        platform_block = store.build_prompt_block(["termit-platform"])
        self.assertIn("Termit Platform", platform_block)
        online_block = store.build_prompt_block(["online-project"])
        self.assertIn("Online Project", online_block)
        web_block = store.build_prompt_block(["web-app"])
        self.assertIn("Web App", web_block)

    def test_skill_select_endpoint(self) -> None:
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/api/platform/skills/select",
            json={
                "instruction": "Fix GitHub Actions CI workflow failure",
                "task_type": "coding",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("fix-ci", payload["selected_skill_ids"])
        self.assertTrue(payload["auto_select_enabled"])

    def test_stub_search_returns_citations(self) -> None:
        provider = StubSearchProvider()
        result = provider.search("termite agent platform")
        self.assertTrue(result.citations)
        self.assertIn("web_search", result.to_observation())

    def test_mcp_registry_invoke_stub(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = McpRegistryService(str(Path(tmp) / "mcp.json"))
            server = registry.upsert_server(
                name="demo",
                command="stub",
                args=[],
                allowed_tools=["ping"],
            )
            payload = registry.invoke_tool(server.server_id, "ping", {"x": 1})
            self.assertIn("stub_ok", payload)
            with self.assertRaises(ValueError):
                registry.invoke_tool(server.server_id, "blocked", {})

    def test_mcp_registry_server_allowed_tools_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = McpRegistryService(str(Path(tmp) / "mcp.json"))
            created = registry.upsert_server(
                name="with-tools",
                command="stub",
                args=[],
                allowed_tools=["ping", "search"],
            )
            self.assertEqual(created.allowed_tools, ["ping", "search"])
            loaded = registry.get_server(created.server_id)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.allowed_tools, ["ping", "search"])

    def test_mcp_registry_invoke_stdio_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = McpRegistryService(str(Path(tmp) / "mcp.json"))
            server = registry.upsert_server(
                name="echo-json",
                command="python3",
                args=[
                    "-c",
                    "import sys,json; print(json.dumps({'status':'ok','echo':json.loads(sys.stdin.read())}))",
                ],
                allowed_tools=["ping"],
            )
            payload = registry.invoke_tool(server.server_id, "ping", {"x": 1})
            self.assertIn('"status": "ok"', payload)
            audit_path = Path(tmp) / "mcp_audit.jsonl"
            self.assertTrue(audit_path.is_file())

    def test_trace_span_store_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TraceSpanStore(str(Path(tmp) / "spans.db"))
            span_id = store.record(run_id="run_test", name="tool.read_file", detail="ok")
            store.record(run_id="run_test", name="provider.ollama", detail="model=llama3")
            store.record(run_id="run_test", name="verify.stage", status="ok", detail="exit_code=0")
            spans = store.list_for_run("run_test")
            self.assertEqual(len(spans), 3)
            span_ids = {item["span_id"] for item in spans}
            self.assertIn(span_id, span_ids)
            names = {item["name"] for item in spans}
            self.assertIn("provider.ollama", names)
            self.assertIn("verify.stage", names)

    def test_mcp_registry_loads_wrapped_servers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mcp.json"
            path.write_text(
                json.dumps(
                    {
                        "servers": [
                            {
                                "server_id": "github-publish",
                                "name": "GitHub",
                                "command": "npx",
                                "args": ["-y", "demo"],
                                "enabled": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            registry = McpRegistryService(str(path))
            servers = registry.list_servers()
            self.assertEqual(len(servers), 1)
            self.assertEqual(servers[0].server_id, "github-publish")

    def test_mcp_registry_import_cursor_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "cursor-mcp.json"
            source.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "Exa Search": {
                                "command": "npx",
                                "args": ["-y", "exa-mcp"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            registry_path = Path(tmp) / "registry.json"
            registry = McpRegistryService(str(registry_path))
            imported = registry.import_from_mcp_file(source, merge=True)
            self.assertEqual(len(imported), 1)
            self.assertEqual(imported[0].command, "npx")
            self.assertEqual(len(registry.list_servers()), 1)

    def test_mcp_registry_import_preserves_allowed_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "registry.json"
            source.write_text(
                json.dumps(
                    {
                        "servers": [
                            {
                                "server_id": "srv_1",
                                "name": "srv",
                                "command": "stub",
                                "args": [],
                                "allowed_tools": ["a", "b"],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            registry = McpRegistryService(str(Path(tmp) / "target.json"))
            imported = registry.import_from_mcp_file(source, merge=True)
            self.assertEqual(imported[0].allowed_tools, ["a", "b"])

    def test_hook_service_runs_local_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "hook.out"
            config = Path(tmp) / "hooks.json"
            config.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "hooks": {
                            "run.stop": [
                                {
                                    "command": (
                                        f"python3 -c \"import sys, pathlib; "
                                        f"pathlib.Path('{output}').write_text(sys.stdin.read())\""
                                    )
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            hooks = AgentHookService(str(config), webhook_url="", enabled=True)
            hooks.emit(
                HookEvent(
                    event_type="run.stop",
                    run_id="r1",
                    agent_id="a1",
                    state="completed",
                )
            )
            self.assertTrue(output.is_file())
            self.assertIn("run.stop", output.read_text(encoding="utf-8"))

    def test_hook_service_emit_no_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "hooks.json"
            config.write_text('{"version":1,"hooks":{"run.stop":[]}}', encoding="utf-8")
            hooks = AgentHookService(str(config), webhook_url="", enabled=True)
            hooks.emit(
                HookEvent(
                    event_type="run.stop",
                    run_id="r1",
                    agent_id="a1",
                    state="completed",
                )
            )
            self.assertIn("run.stop", hooks.list_configured_events())


if __name__ == "__main__":
    unittest.main()
