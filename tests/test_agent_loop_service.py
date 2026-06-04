from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import (
    AgentProfileCreateRequest,
    AgentRunRequest,
    ChatResponse,
    TaskType,
)
from app.services.agent_loop_service import AgentLoopService, build_tool_arguments
from app.services.agent_registry_store import AgentRegistryStore
from app.services.agent_run_store import InMemoryAgentRunStore
from app.services.agent_service import AgentService
from app.services.tooling_service import ToolingService


class LoopChatStub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def chat(self, payload):  # type: ignore[no-untyped-def]
        self.calls += 1
        if not self._responses:
            raise RuntimeError("No more stub responses")
        text = self._responses.pop(0)
        model = payload.model or "ollama:test"
        return ChatResponse(
            provider="ollama",
            model=model,
            task_type=payload.task_type,
            session_id=payload.session_id or "sess-loop",
            history_size=len(payload.history) + 1,
            attempted_models=[model],
            response=text,
        )


class AgentLoopIntegrationTests(unittest.TestCase):
    def test_build_tool_arguments_apply_patch(self) -> None:
        built = build_tool_arguments(
            "apply_patch",
            {
                "path": "app/example.py",
                "hunks": [{"old_text": "a", "new_text": "b"}],
                "dry_run": True,
                "confirmed": False,
            },
        )
        self.assertEqual(built.path, "app/example.py")
        self.assertTrue(built.dry_run)
        self.assertEqual(len(built.hunks), 1)

    def test_tool_loop_invokes_apply_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sample.txt"
            target.write_text("hello world", encoding="utf-8")

            chat = LoopChatStub(
                [
                    json.dumps(
                        {
                            "action": "tool",
                            "tool": "apply_patch",
                            "arguments": {
                                "path": "sample.txt",
                                "hunks": [{"old_text": "hello", "new_text": "hello patched"}],
                                "dry_run": False,
                                "confirmed": True,
                            },
                        }
                    ),
                    json.dumps({"action": "final", "answer": "Patch applied."}),
                ]
            )
            service = AgentService(
                chat_service=chat,
                registry=AgentRegistryStore(file_path=str(Path(tmp) / "agents.json")),
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=object(),  # type: ignore[arg-type]
                agent_loop_service=AgentLoopService(),
                max_concurrency=1,
            )
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Patch Agent",
                    description="loop patch",
                    system_prompt="Apply patches safely.",
                    task_type=TaskType.coding,
                    enabled_tools=["apply_patch"],
                    use_tool_loop=True,
                )
            )
            result = asyncio.run(
                service.run_agent(agent.agent_id, AgentRunRequest(input="Patch sample file"))
            )
            self.assertIn("Patch applied", result.response)
            self.assertIn("hello patched", target.read_text(encoding="utf-8"))

    def test_verify_after_patch_records_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sample.txt"
            target.write_text("value=1", encoding="utf-8")

            chat = LoopChatStub(
                [
                    json.dumps(
                        {
                            "action": "tool",
                            "tool": "apply_patch",
                            "arguments": {
                                "path": "sample.txt",
                                "content": "value=2",
                                "dry_run": False,
                                "confirmed": True,
                            },
                        }
                    ),
                    json.dumps({"action": "final", "answer": "done"}),
                ]
            )
            service = AgentService(
                chat_service=chat,
                registry=AgentRegistryStore(file_path=str(Path(tmp) / "agents.json")),
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=object(),  # type: ignore[arg-type]
                agent_loop_service=AgentLoopService(),
                verify_after_patch=True,
                verify_cmd="echo verify-ok",
                max_concurrency=1,
            )
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Verify Agent",
                    description="verify after patch",
                    system_prompt="Patch and verify.",
                    task_type=TaskType.coding,
                    enabled_tools=["apply_patch", "execute_command"],
                    use_tool_loop=True,
                )
            )
            result = asyncio.run(
                service.run_agent(agent.agent_id, AgentRunRequest(input="Update value"))
            )
            self.assertEqual(result.response, "done")
            self.assertEqual(target.read_text(encoding="utf-8"), "value=2")


    def test_verify_after_patch_auto_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tests_dir = Path(tmp) / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_ok.py").write_text(
                "import unittest\nclass OkTest(unittest.TestCase):\n"
                "    def test_ok(self):\n        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            target = Path(tmp) / "sample.txt"
            target.write_text("value=1", encoding="utf-8")

            chat = LoopChatStub(
                [
                    json.dumps(
                        {
                            "action": "tool",
                            "tool": "apply_patch",
                            "arguments": {
                                "path": "sample.txt",
                                "content": "value=2",
                                "dry_run": False,
                                "confirmed": True,
                            },
                        }
                    ),
                    json.dumps({"action": "final", "answer": "done"}),
                ]
            )
            service = AgentService(
                chat_service=chat,
                registry=AgentRegistryStore(file_path=str(Path(tmp) / "agents.json")),
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=object(),  # type: ignore[arg-type]
                agent_loop_service=AgentLoopService(),
                verify_after_patch=True,
                verify_cmd="",
                max_concurrency=1,
            )
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Auto Verify Agent",
                    description="auto verify cmd",
                    system_prompt="Patch and verify.",
                    task_type=TaskType.coding,
                    enabled_tools=["apply_patch", "execute_command"],
                    use_tool_loop=True,
                )
            )
            result = asyncio.run(
                service.run_agent(agent.agent_id, AgentRunRequest(input="Update value"))
            )
            self.assertEqual(result.response, "done")
            self.assertEqual(target.read_text(encoding="utf-8"), "value=2")

    def test_single_instruction_file_create_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "tmp" / "from_instruction.txt"
            chat = LoopChatStub([json.dumps({"action": "final", "answer": "done"})])
            service = AgentService(
                chat_service=chat,
                registry=AgentRegistryStore(file_path=str(Path(tmp) / "agents.json")),
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=object(),  # type: ignore[arg-type]
                agent_loop_service=AgentLoopService(),
                max_concurrency=1,
            )
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Instruction File Agent",
                    description="single instruction fallback",
                    system_prompt="Follow instruction exactly.",
                    task_type=TaskType.coding,
                    enabled_tools=["apply_patch"],
                    use_tool_loop=True,
                )
            )
            result = asyncio.run(
                service.run_agent(
                    agent.agent_id,
                    AgentRunRequest(
                        input="Create file tmp/from_instruction.txt with exact text fallback-ok and finish."
                    ),
                )
            )
            self.assertEqual(result.response, "done")
            self.assertTrue(target.is_file())
            self.assertEqual(target.read_text(encoding="utf-8").strip(), "fallback-ok")

    def test_verify_not_invoked_without_mutating_tools(self) -> None:
        chat = LoopChatStub([json.dumps({"action": "final", "answer": "only final"})])
        profile = AgentProfileCreateRequest(
            name="Verify Skip Agent",
            description="verify skip for non-mutation",
            system_prompt="Answer directly.",
            task_type=TaskType.general,
            enabled_tools=["read_file"],
            use_tool_loop=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            service = AgentService(
                chat_service=chat,
                registry=AgentRegistryStore(file_path=str(Path(tmp) / "agents.json")),
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=object(),  # type: ignore[arg-type]
                agent_loop_service=AgentLoopService(),
                verify_after_patch=True,
                verify_cmd="python3 -m unittest discover -s tests -q",
                max_concurrency=1,
            )
            created = service.create_agent(profile)
            result = asyncio.run(
                service.run_agent(created.agent_id, AgentRunRequest(input="проверка работы"))
            )
            self.assertEqual(result.response, "only final")

    def test_final_not_blocked_for_non_file_instruction(self) -> None:
        chat = LoopChatStub([json.dumps({"action": "final", "answer": "ok"})])
        profile = AgentProfileCreateRequest(
            name="No File Write Agent",
            description="do not require apply_patch for non file tasks",
            system_prompt="Answer directly.",
            task_type=TaskType.general,
            enabled_tools=["apply_patch", "list_files", "read_file"],
            use_tool_loop=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            service = AgentService(
                chat_service=chat,
                registry=AgentRegistryStore(file_path=str(Path(tmp) / "agents.json")),
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=object(),  # type: ignore[arg-type]
                agent_loop_service=AgentLoopService(),
                max_concurrency=1,
            )
            created = service.create_agent(profile)
            result = asyncio.run(
                service.run_agent(
                    created.agent_id,
                    AgentRunRequest(
                        input="Сделай 2 шага: 1) list_files в path app pattern *.py 2) кратко опиши, что ты сделал."
                    ),
                )
            )
            self.assertEqual(result.response, "ok")

    def test_build_wrapper_uses_user_task_for_file_write_detection(self) -> None:
        chat = LoopChatStub([json.dumps({"action": "final", "answer": "ok"})])
        profile = AgentProfileCreateRequest(
            name="Build Wrapped Agent",
            description="build prompt wrapper shouldn't force apply_patch",
            system_prompt="Answer directly.",
            task_type=TaskType.general,
            enabled_tools=["apply_patch", "list_files", "read_file"],
            use_tool_loop=True,
        )
        wrapped_input = (
            "Ты Termit Builder в режиме Cursor-like one-window.\n"
            "## Фаза 1 — PLAN (без apply_patch)\n"
            "## Фаза 3 — SCAFFOLD\n"
            "## Фаза 4 — IMPLEMENT\n"
            "---\n"
            "Задача пользователя:\n"
            "Сделай обзор repo и опиши, что можно улучшить."
        )
        with tempfile.TemporaryDirectory() as tmp:
            service = AgentService(
                chat_service=chat,
                registry=AgentRegistryStore(file_path=str(Path(tmp) / "agents.json")),
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=object(),  # type: ignore[arg-type]
                agent_loop_service=AgentLoopService(),
                max_concurrency=1,
            )
            created = service.create_agent(profile)
            result = asyncio.run(
                service.run_agent(
                    created.agent_id,
                    AgentRunRequest(input=wrapped_input),
                )
            )
            self.assertEqual(result.response, "ok")

    def test_plan_mode_blocks_mutating_tools(self) -> None:
        chat = LoopChatStub(
            [
                json.dumps(
                    {
                        "action": "tool",
                        "tool": "apply_patch",
                        "arguments": {"path": "README.md", "content": "x", "confirmed": True},
                    }
                ),
                json.dumps({"action": "final", "answer": "plan ok"}),
            ]
        )
        profile = AgentProfileCreateRequest(
            name="Plan Guard Agent",
            description="plan mode blocks mutation",
            system_prompt="Return a plan in plan mode.",
            task_type=TaskType.general,
            enabled_tools=["list_files", "read_file", "apply_patch", "execute_command"],
            use_tool_loop=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            service = AgentService(
                chat_service=chat,
                registry=AgentRegistryStore(file_path=str(Path(tmp) / "agents.json")),
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=object(),  # type: ignore[arg-type]
                agent_loop_service=AgentLoopService(),
                max_concurrency=1,
            )
            created = service.create_agent(profile)
            result = asyncio.run(
                service.run_agent(
                    created.agent_id,
                    AgentRunRequest(input="Сделай план без изменений файлов.", run_mode="plan"),
                )
            )
            self.assertEqual(result.response, "plan ok")


if __name__ == "__main__":
    unittest.main()
