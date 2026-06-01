from __future__ import annotations

import unittest

from app.domain.schemas import TaskType
from app.services.agent_tool_schema import build_openai_tools
from app.services.loop_step_budget import resolve_loop_step_budget, should_escalate_model
from app.services.model_router import ModelRouter
from tests.test_chat_service import build_router


class Phase1Tests(unittest.TestCase):
    def test_build_openai_tools_respects_enabled_list(self) -> None:
        tools = build_openai_tools(["list_files", "read_file"])
        names = [item["function"]["name"] for item in tools]  # type: ignore[index]
        self.assertEqual(names, ["list_files", "read_file"])

    def test_resolve_loop_step_budget_scales_with_task(self) -> None:
        from app.domain.schemas import AgentProfileCreateRequest, AgentProfileResponse, AgentRunRequest

        profile = AgentProfileResponse(
            agent_id="a1",
            name="t",
            description="d",
            system_prompt="s",
            task_type=TaskType.coding,
            enabled_tools=["list_files"],
            max_tool_steps=6,
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )
        short = resolve_loop_step_budget(profile, AgentRunRequest(input="fix bug"))
        long = resolve_loop_step_budget(
            profile,
            AgentRunRequest(input="refactor architecture " + ("x" * 500)),
        )
        self.assertGreaterEqual(long, short)

    def test_should_escalate_model(self) -> None:
        self.assertTrue(should_escalate_model(parse_errors=2, verify_failures=0, repeat_blocks=0))
        self.assertFalse(should_escalate_model(parse_errors=0, verify_failures=0, repeat_blocks=0))

    def test_model_profile_alias(self) -> None:
        router = build_router()
        resolved = router.resolve_profile_model("coding-fast")
        self.assertTrue(resolved.startswith("ollama:") or resolved.startswith("openai_compat:"))


if __name__ == "__main__":
    unittest.main()
