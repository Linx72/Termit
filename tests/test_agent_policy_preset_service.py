import unittest

from app.domain.schemas import AgentProfileResponse, AgentRunRequest, TaskType
from app.services.agent_policy_preset_service import AgentPolicyPresetService


class AgentPolicyPresetServiceTests(unittest.TestCase):
    def test_preset_does_not_expand_agent_tool_allowlist(self) -> None:
        service = AgentPolicyPresetService("data/desktop_policy_presets.json")
        profile = AgentProfileResponse(
            agent_id="agt_test",
            name="Test",
            description="",
            system_prompt="You are test agent.",
            task_type=TaskType.coding,
            enabled_tools=["web_automation"],
            use_tool_loop=True,
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )
        payload = AgentRunRequest(input="Улучши UI и добавь README", policy_preset="strict")
        updated_profile, _updated_payload = service.apply_to_run(profile, payload)
        self.assertEqual(updated_profile.enabled_tools, [])


if __name__ == "__main__":
    unittest.main()
