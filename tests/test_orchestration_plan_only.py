from __future__ import annotations

import unittest

from app.domain.schemas import OrchestrationRunRequest, TaskType
from app.services.multi_agent_orchestrator import MultiAgentOrchestrator


class PlanOnlyOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_plan_only_skips_executor(self) -> None:
        class FakeChat:
            async def chat(self, _payload):
                raise AssertionError("chat should not run in plan_only mode")

        orchestrator = MultiAgentOrchestrator(
            task_service=object(),  # type: ignore[arg-type]
            chat_service=FakeChat(),  # type: ignore[arg-type]
            tooling=None,
            code_retrieval=None,
        )

        async def fake_planner(_payload):
            return ["step-a", "step-b"]

        async def fake_explore(_payload):
            return "found auth in app/services"

        orchestrator._planner_steps = fake_planner  # type: ignore[method-assign]
        orchestrator._parallel_explore = fake_explore  # type: ignore[method-assign]

        result = await orchestrator.run(
            OrchestrationRunRequest(
                input="Refactor auth module",
                task_type=TaskType.coding,
                plan_only=True,
            )
        )
        self.assertEqual(result.status, "plan_ready")
        self.assertEqual(result.plan_steps, ["step-a", "step-b"])
        self.assertIn("Plan-only", result.report)


if __name__ == "__main__":
    unittest.main()
