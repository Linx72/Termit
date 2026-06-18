import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    async def test_coder_retries_on_reviewer_issues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            router = build_router()
            providers: dict[str, BaseProvider] = {
                "ollama": SequencedProvider(
                    [
                        "1. analyze\n2. implement\n3. verify",
                        "First draft with missing tests.",
                        "ISSUES: missing tests and explicit file updates.",
                        "Implemented patch with tests and explicit file list.",
                        "APPROVED: ready to ship.",
                    ]
                ),
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
                    input="Fix flaky test and update docs",
                    task_type=TaskType.coding,
                    use_retrieval=False,
                )
            )
            self.assertEqual(result.status, "completed")
            self.assertIn("Implemented patch with tests", result.executor_response)
            metrics = orchestrator.metrics_snapshot()
            self.assertGreaterEqual(metrics["orchestration_runs_total"], 1)
            self.assertGreaterEqual(metrics["coder_retry_runs_total"], 1)
            self.assertGreater(metrics["avg_coder_attempts"], 1.0)

    async def test_openhands_contract_enabled_captures_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            router = build_router()
            providers: dict[str, BaseProvider] = {
                "ollama": SequencedProvider(
                    [
                        "1. analyze\n2. implement\n3. verify",
                        "Implemented patch and tests in app/services/demo.py",
                        "APPROVED: all good.",
                    ]
                ),
                "openai_compat": StubProvider(response="fallback"),
            }
            chat = ChatService(router, providers, MemoryStore(), cache_ttl_seconds=0)
            tasks = TaskService(ToolingService(root_path="."), InMemoryTaskStore(), max_attempts=2)
            orchestrator = MultiAgentOrchestrator(
                tasks,
                chat,
                tooling=ToolingService(root_path=tmp),
                openhands_contract_enabled=True,
            )

            result = await orchestrator.run(
                OrchestrationRunRequest(
                    input="Fix bug and add tests",
                    task_type=TaskType.coding,
                    use_retrieval=False,
                )
            )
            self.assertEqual(result.status, "completed")
            self.assertGreaterEqual(len(result.action_observation), 4)
            self.assertTrue(any(item.action.startswith("coder.attempt_") for item in result.action_observation))
            self.assertIn("OpenHands action/observation", result.report)
            metrics = orchestrator.metrics_snapshot()
            self.assertGreaterEqual(metrics["openhands_contract_runs_total"], 1)
            self.assertGreater(metrics["openhands_contract_actions_total"], 0)

    async def test_tool_loop_execution_enabled_runs_tool_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "README.md").write_text("hello tool loop", encoding="utf-8")
            router = build_router()
            providers: dict[str, BaseProvider] = {
                "ollama": SequencedProvider(
                    [
                        "1. inspect\n2. update\n3. verify",
                        (
                            '{"tool_actions":['
                            '{"tool":"list_files","path":".","pattern":"*.md"},'
                            '{"tool":"read_file","path":"README.md","max_bytes":2000}'
                            ']}'
                        ),
                        "APPROVED: tools executed.",
                    ]
                ),
                "openai_compat": StubProvider(response="fallback"),
            }
            chat = ChatService(router, providers, MemoryStore(), cache_ttl_seconds=0)
            tasks = TaskService(ToolingService(root_path="."), InMemoryTaskStore(), max_attempts=2)
            orchestrator = MultiAgentOrchestrator(
                tasks,
                chat,
                tooling=ToolingService(root_path=tmp),
                tool_loop_execution_enabled=True,
            )
            result = await orchestrator.run(
                OrchestrationRunRequest(
                    input="Inspect workspace and summarize markdown file",
                    task_type=TaskType.coding,
                    use_retrieval=False,
                )
            )
            self.assertEqual(result.status, "completed")
            phase_names = {item.phase for item in result.phases}
            self.assertIn("coder_tool_loop", phase_names)
            metrics = orchestrator.metrics_snapshot()
            self.assertGreaterEqual(metrics["orchestration_tool_loop_runs_total"], 1)
            self.assertGreaterEqual(metrics["orchestration_tool_steps_total"], 1)

    async def test_eval_fixture_coder_runs_tool_loop_without_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "README.md").write_text("fixture readme", encoding="utf-8")
            router = build_router()
            chat = ChatService(router, {}, MemoryStore(), cache_ttl_seconds=0)
            tasks = TaskService(ToolingService(root_path="."), InMemoryTaskStore(), max_attempts=2)
            orchestrator = MultiAgentOrchestrator(
                tasks,
                chat,
                tooling=ToolingService(root_path=tmp),
                tool_loop_execution_enabled=True,
                eval_fixture_coder_enabled=True,
            )
            result = await orchestrator.run(
                OrchestrationRunRequest(
                    input="ORCH11 fixture scenario",
                    task_type=TaskType.coding,
                    use_retrieval=False,
                    eval_fixture=True,
                )
            )
            phase_names = {item.phase for item in result.phases}
            self.assertIn("coder_tool_loop", phase_names)
            metrics = orchestrator.metrics_snapshot()
            self.assertGreaterEqual(metrics["orchestration_tool_steps_total"], 1)
            self.assertEqual(metrics["orchestration_tool_loop_fallback_total"], 0.0)

    async def test_tool_loop_retries_when_first_response_has_no_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "README.md").write_text("retry path", encoding="utf-8")
            router = build_router()
            providers: dict[str, BaseProvider] = {
                "ollama": SequencedProvider(
                    [
                        "I will inspect files and summarize markdown docs for you.",
                        '{"tool_actions":[{"tool":"list_files","path":".","pattern":"*.md"}]}',
                        "APPROVED: tool loop executed.",
                    ]
                ),
                "openai_compat": StubProvider(response="fallback"),
            }
            chat = ChatService(router, providers, MemoryStore(), cache_ttl_seconds=0)
            tasks = TaskService(ToolingService(root_path="."), InMemoryTaskStore(), max_attempts=2)
            orchestrator = MultiAgentOrchestrator(
                tasks,
                chat,
                tooling=ToolingService(root_path=tmp),
                tool_loop_execution_enabled=True,
                eval_fixture_coder_enabled=False,
            )
            result = await orchestrator.run(
                OrchestrationRunRequest(
                    input="Inspect markdown files via tool actions",
                    task_type=TaskType.coding,
                    use_retrieval=False,
                    model="ollama:test",
                )
            )
            self.assertEqual(result.status, "completed")
            metrics = orchestrator.metrics_snapshot()
            self.assertGreaterEqual(metrics["orchestration_tool_steps_total"], 1)
            self.assertEqual(metrics["orchestration_tool_loop_fallback_total"], 0.0)

    async def test_strict_mode_retries_when_reviewer_approves_without_tool_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "README.md").write_text("strict retry path", encoding="utf-8")
            router = build_router()
            providers: dict[str, BaseProvider] = {
                "ollama": SequencedProvider(
                    [
                        "Summary without JSON tool actions.",
                        "APPROVED: looks fine.",
                        '{"tool_actions":[{"tool":"list_files","path":".","pattern":"*.md"}]}',
                        "APPROVED: tool loop executed.",
                    ]
                ),
                "openai_compat": StubProvider(response="fallback"),
            }
            chat = ChatService(router, providers, MemoryStore(), cache_ttl_seconds=0)
            tasks = TaskService(ToolingService(root_path="."), InMemoryTaskStore(), max_attempts=2)
            orchestrator = MultiAgentOrchestrator(
                tasks,
                chat,
                tooling=ToolingService(root_path=tmp),
                tool_loop_execution_enabled=True,
                eval_fixture_coder_enabled=False,
            )
            with patch.dict(os.environ, {"TERMIT_ORCH_TOOL_LOOP_FALLBACK": "false"}, clear=False):
                result = await orchestrator.run(
                    OrchestrationRunRequest(
                        input="Inspect markdown files via tool actions",
                        task_type=TaskType.coding,
                        use_retrieval=False,
                        model="ollama:test",
                    )
                )
            self.assertEqual(result.status, "completed")
            metrics = orchestrator.metrics_snapshot()
            self.assertGreaterEqual(metrics["orchestration_tool_steps_total"], 1)
            self.assertEqual(metrics["orchestration_tool_loop_fallback_total"], 0.0)

    async def test_tool_loop_fallback_when_model_omits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "README.md").write_text("fallback path", encoding="utf-8")
            router = build_router()
            providers: dict[str, BaseProvider] = {
                "ollama": SequencedProvider(
                    [
                        "I will inspect markdown files and summarize findings.",
                        "APPROVED: summary looks good.",
                    ]
                ),
                "openai_compat": StubProvider(response="fallback"),
            }
            chat = ChatService(router, providers, MemoryStore(), cache_ttl_seconds=0)
            tasks = TaskService(ToolingService(root_path="."), InMemoryTaskStore(), max_attempts=2)
            orchestrator = MultiAgentOrchestrator(
                tasks,
                chat,
                tooling=ToolingService(root_path=tmp),
                tool_loop_execution_enabled=True,
                eval_fixture_coder_enabled=False,
            )
            result = await orchestrator.run(
                OrchestrationRunRequest(
                    input="Inspect markdown via tool actions",
                    task_type=TaskType.coding,
                    use_retrieval=False,
                    model="ollama:test",
                )
            )
            self.assertEqual(result.status, "completed")
            metrics = orchestrator.metrics_snapshot()
            self.assertGreaterEqual(metrics["orchestration_tool_steps_total"], 1)
            self.assertGreaterEqual(metrics["orchestration_tool_loop_fallback_total"], 1.0)
            tool_phases = [item for item in result.phases if item.phase == "coder_tool_loop"]
            self.assertTrue(tool_phases)
            self.assertEqual(tool_phases[0].status, "passed")

    async def test_orchestration_survives_provider_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            router = build_router()
            chat = ChatService(router, {}, MemoryStore(), cache_ttl_seconds=0)
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
            self.assertEqual(result.status, "failed")
            coder_phases = [item for item in result.phases if item.phase == "coder"]
            self.assertEqual(len(coder_phases), 1)
            self.assertEqual(coder_phases[0].status, "failed")


class SequencedProvider(BaseProvider):
    name = "sequence"

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    async def generate(
        self,
        model_name: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        if self._responses:
            return self._responses.pop(0)
        return "APPROVED"

    def list_models(self) -> list[str]:
        return ["sequence:model"]

    async def check_health(self) -> tuple[bool, str]:
        return (True, "ok")


if __name__ == "__main__":
    unittest.main()
