from __future__ import annotations

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

    def test_skill_store_lists_bundled_skills(self) -> None:
        root = Path(__file__).resolve().parents[1] / "data" / "skills"
        store = SkillStore(str(root))
        skills = store.list_skills()
        ids = {item.skill_id for item in skills}
        self.assertIn("fix-ci", ids)
        block = store.build_prompt_block(["fix-ci"])
        self.assertIn("Fix CI", block)

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
            spans = store.list_for_run("run_test")
            self.assertEqual(len(spans), 1)
            self.assertEqual(spans[0]["span_id"], span_id)

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
