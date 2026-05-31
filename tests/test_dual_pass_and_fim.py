import asyncio
import unittest

from app.core.config import Settings
from app.domain.schemas import ChatRequest, FimCompletionRequest, TaskCreateRequest, TaskMode, TaskType
from app.services.chat_service import ChatService
from app.services.memory_store import MemoryStore
from app.services.model_router import ModelRouter
from app.services.providers.base import BaseProvider
from app.services.task_service import TaskService
from app.services.task_store import InMemoryTaskStore
from app.services.tooling_service import ToolingService


class SequenceProvider(BaseProvider):
    name = "stub"

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    async def generate(
        self,
        model_name: str,
        messages,
        temperature: float,
        max_tokens: int,
    ) -> str:
        index = min(self.calls, len(self.responses) - 1)
        value = self.responses[index]
        self.calls += 1
        return value

    def list_models(self) -> list[str]:
        return ["stub:draft", "stub:review"]

    async def check_health(self) -> tuple[bool, str]:
        return True, "ok"


def build_test_settings() -> Settings:
    return Settings(
        host="0.0.0.0",
        port=8765,
        allowed_origins=["*"],
        default_model="stub:draft",
        code_model="stub:draft",
        analysis_model="stub:review",
        default_fallback_model="stub:review",
        code_fallback_model="stub:review",
        analysis_fallback_model="stub:review",
        ollama_base_url="http://localhost:11434",
        openai_compat_base_url="http://localhost:8001",
        openai_compat_api_key="",
        memory_backend="memory",
        memory_sqlite_path="./test_memory.db",
        memory_max_messages=40,
        auth_enabled=False,
        api_keys={},
        quota_sqlite_path="./test_quota.db",
        default_daily_quota=1000,
        default_api_role="operator",
        feedback_file_path="./data/feedback.jsonl",
        circuit_failure_threshold=3,
        circuit_cooldown_seconds=60,
        eval_scenarios_path="./data/eval_scenarios.json",
        task_backend="memory",
        task_sqlite_path="./test_tasks.db",
        agent_registry_file_path="./data/agents.test.json",
    )


class DualPassAndFimTests(unittest.TestCase):
    def _service(self, provider: BaseProvider, *, dual_pass: bool = False) -> ChatService:
        router = ModelRouter(build_test_settings())
        return ChatService(
            router,
            {"stub": provider},
            MemoryStore(),
            dual_pass_enabled=dual_pass,
            dual_pass_task_types="coding,review,debug",
            retrieval_enabled=False,
        )

    def test_dual_pass_keeps_draft_when_approved(self) -> None:
        provider = SequenceProvider(["draft answer", "APPROVED"])
        service = self._service(provider, dual_pass=True)
        result = asyncio.run(
            service.chat(
                ChatRequest(message="Fix bug", task_type=TaskType.coding, use_memory=False)
            )
        )
        self.assertEqual(result.response, "draft answer")
        self.assertTrue(result.dual_pass_used)
        self.assertEqual(provider.calls, 2)

    def test_dual_pass_replaces_draft_when_rejected(self) -> None:
        provider = SequenceProvider(["bad draft", "improved final"])
        service = self._service(provider, dual_pass=True)
        result = asyncio.run(
            service.chat(
                ChatRequest(message="Fix bug", task_type=TaskType.coding, use_memory=False)
            )
        )
        self.assertEqual(result.response, "improved final")
        self.assertTrue(result.dual_pass_used)

    def test_fim_strips_multiline_blocks(self) -> None:
        provider = SequenceProvider(["  insert_me  "])
        service = self._service(provider)
        result = asyncio.run(
            service.fim_complete(
                FimCompletionRequest(prefix="def foo():\n    ", suffix="\n    pass")
            )
        )
        self.assertEqual(result.insert_text, "insert_me")
        self.assertEqual(provider.calls, 1)


class TaskAgentBridgeTests(unittest.TestCase):
    def test_auto_task_uses_agent_runner(self) -> None:
        tooling = ToolingService(root_path=".")
        store = InMemoryTaskStore()

        def runner(input_text: str, task_type: TaskType, session_id: str | None) -> str:
            self.assertEqual(input_text, "Implement retry helper")
            self.assertEqual(task_type, TaskType.coding)
            return "Agent finished with patch and tests."

        service = TaskService(
            tooling,
            store,
            agent_runner=runner,
            use_agent_for_auto=True,
        )
        created = service.create_task(
            TaskCreateRequest(
                input="Implement retry helper",
                task_type=TaskType.coding,
                mode=TaskMode.auto,
            )
        )
        task = service.get_task(created.task_id)
        self.assertEqual(task.state.value, "completed")
        self.assertIn("Agent finished", task.report or "")


if __name__ == "__main__":
    unittest.main()
