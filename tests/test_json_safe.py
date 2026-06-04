import json
import unittest

from app.services.agent_hook_service import AgentHookService, HookEvent
from app.services.agent_loop_service import _tool_fingerprint
from app.services.json_safe import json_dumps, json_safe
from app.services.tool_json_parser import parse_loop_action


class JsonSafeTests(unittest.TestCase):
    def test_json_safe_converts_sets(self) -> None:
        payload = {"tags": {"alpha", "beta"}, "items": [1, 2]}
        sanitized = json_safe(payload)
        json.dumps(sanitized)
        self.assertEqual(sanitized["tags"], ["alpha", "beta"])

    def test_tool_fingerprint_accepts_set_arguments(self) -> None:
        fingerprint = _tool_fingerprint("list_files", {"tags": {"py", "app"}})
        self.assertIn("list_files", fingerprint)

    def test_parse_loop_action_sanitizes_set_arguments(self) -> None:
        action = parse_loop_action(
            '{"action":"tool","tool":"list_files","arguments":{"path":".","tags":{"a","b"}}}'
        )
        self.assertEqual(action["action"], "tool")
        arguments = action["arguments"]
        self.assertIsInstance(arguments, dict)
        json.dumps(arguments)
        self.assertEqual(arguments["tags"], ["a", "b"])

    def test_json_dumps_accepts_checkpoint_with_set_arguments(self) -> None:
        checkpoint = {
            "pending_tool": "apply_patch",
            "pending_arguments": {"paths": {"app/main.py"}},
            "step": 2,
        }
        encoded = json_dumps(checkpoint, ensure_ascii=True)
        parsed = json.loads(encoded)
        self.assertEqual(parsed["pending_arguments"]["paths"], ["app/main.py"])

    def test_hook_emit_serializes_set_in_extra(self) -> None:
        hooks = AgentHookService(config_path="/nonexistent/hooks.json", enabled=True)
        hooks.emit(
            HookEvent(
                event_type="tool.post_use",
                run_id="r1",
                agent_id="a1",
                state="running",
                extra={"arguments": {"domains": {"example.com"}}},
            )
        )


if __name__ == "__main__":
    unittest.main()
