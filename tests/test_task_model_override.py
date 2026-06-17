"""Tests for task model override and agent run model passthrough."""

from __future__ import annotations

import time
import unittest

from app.domain.schemas import (
    AgentProfileResponse,
    AgentRunRequest,
    TaskCreateRequest,
    TaskType,
)
from app.services.agent_service import AgentService
from app.services.task_service import TaskService
from app.services.task_store import InMemoryTaskStore
from app.services.tooling_service import ToolingService


class TaskModelOverrideTests(unittest.TestCase):
    def test_create_task_stores_model(self) -> None:
        service = TaskService(ToolingService(root_path="."), InMemoryTaskStore())
        created = service.create_task(
            TaskCreateRequest(
                input="Implement helper function",
                task_type=TaskType.coding,
                model="ollama:deepseek-coder",
            )
        )
        task = service.get_task(created.task_id)
        self.assertEqual(task.model, "ollama:deepseek-coder")

    def test_agent_runner_receives_model(self) -> None:
        captured: dict[str, str | None] = {}

        def runner(input_text, task_type, session_id, project_id, model):
            captured["model"] = model
            return "done"

        service = TaskService(
            ToolingService(root_path="."),
            InMemoryTaskStore(),
            agent_runner=runner,
            use_agent_for_auto=True,
        )
        created = service.create_task(
            TaskCreateRequest(
                input="Quick coding task",
                task_type=TaskType.coding,
                model="ollama:termit-core-ft",
            )
        )
        deadline = time.time() + 2.0
        task = service.get_task(created.task_id)
        while task.state.value not in {"completed", "failed", "cancelled"} and time.time() < deadline:
            time.sleep(0.05)
            task = service.get_task(created.task_id)
        self.assertEqual(task.state.value, "completed")
        self.assertEqual(captured["model"], "ollama:termit-core-ft")


class AgentRunModelOverrideTests(unittest.TestCase):
    def test_resolve_run_model_honors_payload_model(self) -> None:
        service = AgentService.__new__(AgentService)
        profile = AgentProfileResponse(
            agent_id="a1",
            name="test",
            description="",
            system_prompt="sys",
            task_type=TaskType.coding,
            model="ollama:default-profile-model",
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )
        payload = AgentRunRequest(input="fix bug", model="ollama:forced-model")
        resolved, escalation = service._resolve_run_model(profile, payload)
        self.assertEqual(resolved, "ollama:forced-model")
        self.assertIsNone(escalation)


if __name__ == "__main__":
    unittest.main()
