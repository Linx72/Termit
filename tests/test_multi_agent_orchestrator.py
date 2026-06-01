import asyncio
import tempfile
import unittest

from app.domain.schemas import ChatMessage, ChatRequest, OrchestrationRunRequest, TaskType
from app.services.chat_service import ChatService
from app.services.memory_store import MemoryStore
from app.services.model_router import ModelRouter
from app.services.multi_agent_orchestrator import MultiAgentOrchestrator
from app.services.providers.base import BaseProvider
from app.services.task_service import TaskService
from app.services.task_store import InMemoryTaskStore
from app.services.tooling_service import ToolingService
from tests.test_chat_service import StubProvider, build_router


class MultiAgentOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_orchestration_run_completes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            router = build_router()
            providers: dict[str, BaseProvider] = {
                "ollama": StubProvider(response="Implemented patch and tests."),
                "openai_compat": StubProvider(response="fallback"),
            }
            chat = ChatService(router, providers, MemoryStore(), cache_ttl_seconds=0)
            tasks = TaskService(ToolingService(root_path="."), InMemoryTaskStore(), max_attempts=2)
            orchestrator = MultiAgentOrchestrator(
                tasks,
                chat,
                tooling=ToolingService(root_path=tmp),
            )

            result = await orchestrator.run(
                OrchestrationRunRequest(
                    input="Refactor module and update README for release",
                    task_type=TaskType.coding,
                    use_retrieval=False,
                )
            )
            self.assertEqual(result.status, "completed")
            self.assertGreaterEqual(len(result.plan_steps), 3)
            phase_names = {item.phase for item in result.phases}
            self.assertTrue({"planner", "coder", "verifier", "task_runner"}.issubset(phase_names))
            self.assertIn("Implemented patch", result.executor_response)


if __name__ == "__main__":
    unittest.main()
