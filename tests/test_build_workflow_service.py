import unittest

from app.services.agent_service import AgentService
from app.services.build_workflow_service import BuildWorkflowService


class BuildWorkflowServiceTests(unittest.TestCase):
    def test_extract_user_task_from_enriched_builder_input(self) -> None:
        enriched = BuildWorkflowService.enrich_agent_input(
            "Добавь endpoint /api/finetune/dpo/status.",
            execution_mode="local",
            workspace="/tmp/proj",
        )
        task = BuildWorkflowService.extract_user_task(enriched)
        self.assertIn("/api/finetune/dpo/status", task)
        self.assertNotIn("Cursor-like", task)

    def test_extract_user_task_passthrough_plain_input(self) -> None:
        plain = "Fix flaky test in test_eval_dashboard.py"
        self.assertEqual(BuildWorkflowService.extract_user_task(plain), plain)

    def test_capture_instruction_prefers_online_objective(self) -> None:
        from app.domain.schemas import AgentRunRequest

        enriched = BuildWorkflowService.enrich_agent_input(
            "Short hidden task",
            execution_mode="local",
            workspace="/tmp",
        )
        payload = AgentRunRequest(
            input=enriched,
            online_objective="Use online objective for capture",
        )
        captured = AgentService._capture_instruction(payload)
        self.assertEqual(captured, "Use online objective for capture")


if __name__ == "__main__":
    unittest.main()
