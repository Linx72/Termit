from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from app.domain.schemas import AgentRunResponse, TaskType
from app.services.agent_eval_service import AgentEvalService


class AgentEvalServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_scenario_scores_substrings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenarios_path = Path(tmp) / "agent_eval.json"
            scenarios_path.write_text(
                """[
                  {
                    "id": "T1",
                    "title": "Dry run mention",
                    "category": "patch_quality",
                    "agent_name": "Test",
                    "system_prompt": "Be concise.",
                    "input": "Explain patch flow",
                    "enabled_tools": ["apply_patch"],
                    "use_tool_loop": false,
                    "expect_substrings": ["dry_run", "confirmed"]
                  }
                ]""",
                encoding="utf-8",
            )
            agent_service = MagicMock()
            agent_service.create_agent.return_value = MagicMock(agent_id="agent-1")
            agent_service.run_agent = AsyncMock(
                return_value=AgentRunResponse(
                    agent_id="agent-1",
                    agent_name="Test",
                    provider="stub",
                    model="test",
                    task_type=TaskType.general,
                    response="Use dry_run first, then confirmed apply.",
                )
            )
            service = AgentEvalService(
                scenarios_path=str(scenarios_path),
                agent_service=agent_service,
            )
            result = await service.run_scenario("T1")
            self.assertTrue(result["success"])
            self.assertEqual(result["scenario_id"], "T1")

    async def test_run_suite_pass_rate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenarios_path = Path(tmp) / "agent_eval.json"
            scenarios_path.write_text(
                """[
                  {"id": "A", "title": "A", "category": "x", "agent_name": "A", "system_prompt": "You are agent A.", "input": "i", "enabled_tools": [], "expect_substrings": ["ok"]},
                  {"id": "B", "title": "B", "category": "x", "agent_name": "B", "system_prompt": "You are agent B.", "input": "i", "enabled_tools": [], "expect_substrings": ["missing"]}
                ]""",
                encoding="utf-8",
            )
            agent_service = MagicMock()
            agent_service.create_agent.return_value = MagicMock(agent_id="agent-x")

            calls = {"n": 0}

            async def _run(agent_id: str, payload):  # noqa: ANN001, ARG001
                calls["n"] += 1
                text = "ok" if calls["n"] == 1 else "nope"
                return AgentRunResponse(
                    agent_id=agent_id,
                    agent_name="Test",
                    provider="stub",
                    model="test",
                    task_type=TaskType.general,
                    response=text,
                )

            agent_service.run_agent = _run
            service = AgentEvalService(
                scenarios_path=str(scenarios_path),
                agent_service=agent_service,
            )
            suite = await service.run_suite()
            self.assertEqual(suite["total"], 2)
            self.assertEqual(suite["passed"], 1)
            self.assertAlmostEqual(suite["pass_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
