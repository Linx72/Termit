from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import (
    AgentProfileCreateRequest,
    AgentRunRequest,
    AgentRunState,
    ChatResponse,
    TaskType,
)
from app.services.agent_loop_service import AgentAwaitingConfirmation, AgentLoopService
from app.services.agent_registry_store import AgentRegistryStore
from app.services.agent_run_store import InMemoryAgentRunStore
from app.services.agent_service import AgentService
from app.services.code_retrieval_service import CodeRetrievalService
from app.services.tooling_service import ToolingService


class LoopChatStub:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    async def chat(self, payload):  # type: ignore[no-untyped-def]
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


class SprintTop5Tests(unittest.TestCase):
    def test_resume_checkpoint_restores_verify_retry_counter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistryStore(file_path=str(Path(tmp) / "agents.json"))
            profile = registry.create_agent(
                AgentProfileCreateRequest(
                    name="resume-verify-agent",
                    description="test",
                    system_prompt="You are a test agent.",
                    task_type=TaskType.coding,
                    enabled_tools=["execute_command"],
                    use_tool_loop=True,
                )
            )
            loop = AgentLoopService()
            stub = LoopChatStub(
                [
                    '{"action":"final","answer":"done after resume"}',
                ]
            )

            def tool_fn(_tool_name: str, _arguments: dict[str, object]) -> str:
                return json.dumps({"executed": True, "exit_code": 0, "stdout": "ok"})

            def verify_fn() -> tuple[bool, str]:
                return (False, "still failing")

            with self.assertRaisesRegex(Exception, "Verify retries exhausted"):
                asyncio.run(
                    loop.run(
                        profile=profile,
                        payload=AgentRunRequest(input="resume verify"),
                        chat_fn=stub.chat,
                        tool_fn=tool_fn,
                        memory_context=[],
                        max_steps=3,
                        verify_fn=verify_fn,
                        max_verify_retries=1,
                        resume_checkpoint={
                            "history": [
                                {"role": "system", "content": "test"},
                                {"role": "user", "content": "resume"},
                            ],
                            "pending_tool": "execute_command",
                            "pending_arguments": {
                                "command": "echo ok",
                                "path": ".",
                                "dry_run": False,
                                "confirmed": True,
                            },
                            "step": 1,
                            "active_model": "ollama:test",
                            "verify_retries_used": 1,
                        },
                    )
                )

    def test_finalize_verify_failure_retries_in_loop_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistryStore(file_path=str(Path(tmp) / "agents.json"))
            profile = registry.create_agent(
                AgentProfileCreateRequest(
                    name="verify-loop-agent",
                    description="test",
                    system_prompt="You are a test agent.",
                    task_type=TaskType.coding,
                    enabled_tools=["execute_command"],
                    use_tool_loop=True,
                )
            )
            loop = AgentLoopService()
            stub = LoopChatStub(
                [
                    '{"action":"tool","tool":"execute_command","arguments":{"command":"echo ok","path":".","dry_run":false,"confirmed":true}}',
                    '{"action":"final","answer":"done"}',
                    '{"action":"final","answer":"done after fix"}',
                ]
            )

            def tool_fn(_tool_name: str, _arguments: dict[str, object]) -> str:
                return json.dumps({"executed": True, "exit_code": 0, "stdout": "ok"})

            verify_results = [(False, "tests failed"), (True, "all good")]

            def verify_fn() -> tuple[bool, str]:
                return verify_results.pop(0)

            result = asyncio.run(
                loop.run(
                    profile=profile,
                    payload=AgentRunRequest(input="run verify"),
                    chat_fn=stub.chat,
                    tool_fn=tool_fn,
                    memory_context=[],
                    max_steps=5,
                    verify_fn=verify_fn,
                    max_verify_retries=1,
                )
            )
            self.assertEqual(result.response, "done after fix")
            actions = [step.action for step in result.steps]
            self.assertIn("verify_retry", actions)
            self.assertIn("verify_pass", actions)

    def test_finalize_verify_failure_exhausted_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistryStore(file_path=str(Path(tmp) / "agents.json"))
            profile = registry.create_agent(
                AgentProfileCreateRequest(
                    name="verify-loop-agent",
                    description="test",
                    system_prompt="You are a test agent.",
                    task_type=TaskType.coding,
                    enabled_tools=["execute_command"],
                    use_tool_loop=True,
                )
            )
            loop = AgentLoopService()
            stub = LoopChatStub(
                [
                    '{"action":"tool","tool":"execute_command","arguments":{"command":"echo ok","path":".","dry_run":false,"confirmed":true}}',
                    '{"action":"final","answer":"done"}',
                    '{"action":"final","answer":"done again"}',
                ]
            )

            def tool_fn(_tool_name: str, _arguments: dict[str, object]) -> str:
                return json.dumps({"executed": True, "exit_code": 0, "stdout": "ok"})

            def verify_fn() -> tuple[bool, str]:
                return (False, "still failing")

            with self.assertRaisesRegex(Exception, "Verify retries exhausted"):
                asyncio.run(
                    loop.run(
                        profile=profile,
                        payload=AgentRunRequest(input="run verify"),
                        chat_fn=stub.chat,
                        tool_fn=tool_fn,
                        memory_context=[],
                        max_steps=5,
                        verify_fn=verify_fn,
                        max_verify_retries=1,
                    )
                )

    def test_repeat_tool_call_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistryStore(file_path=str(Path(tmp) / "agents.json"))
            profile = registry.create_agent(
                AgentProfileCreateRequest(
                    name="loop-agent",
                    description="test",
                    system_prompt="You are a test agent.",
                    task_type=TaskType.coding,
                    enabled_tools=["list_files"],
                    use_tool_loop=True,
                )
            )
            loop = AgentLoopService()
            stub = LoopChatStub(
                [
                    '{"action":"tool","tool":"list_files","arguments":{"path":"."}}',
                    '{"action":"tool","tool":"list_files","arguments":{"path":"."}}',
                    '{"action":"final","answer":"done"}',
                ]
            )
            calls: list[str] = []

            def tool_fn(tool_name: str, _arguments: dict[str, object]) -> str:
                calls.append(tool_name)
                return json.dumps({"files": []})

            result = asyncio.run(
                loop.run(
                    profile=profile,
                    payload=AgentRunRequest(input="list files"),
                    chat_fn=stub.chat,
                    tool_fn=tool_fn,
                    memory_context=[],
                    max_steps=5,
                )
            )
            self.assertEqual(result.response, "done")
            self.assertEqual(calls, ["list_files"])
            self.assertIn("repeat_blocked", [step.action for step in result.steps])

    def test_requires_confirmation_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistryStore(file_path=str(Path(tmp) / "agents.json"))
            profile = registry.create_agent(
                AgentProfileCreateRequest(
                    name="loop-agent",
                    description="test",
                    system_prompt="You are a test agent.",
                    task_type=TaskType.coding,
                    enabled_tools=["apply_patch"],
                    use_tool_loop=True,
                )
            )
            loop = AgentLoopService()
            stub = LoopChatStub(
                [
                    '{"action":"tool","tool":"apply_patch","arguments":{"path":"x.txt","content":"hi","create":true}}',
                ]
            )

            def tool_fn(_tool_name: str, _arguments: dict[str, object]) -> str:
                return json.dumps({"requires_confirmation": True, "path": "x.txt"})

            with self.assertRaises(AgentAwaitingConfirmation) as ctx:
                asyncio.run(
                    loop.run(
                        profile=profile,
                        payload=AgentRunRequest(input="write file"),
                        chat_fn=stub.chat,
                        tool_fn=tool_fn,
                        memory_context=[],
                        max_steps=3,
                    )
                )
            self.assertIn("pending_tool", ctx.exception.checkpoint)

    def test_confirm_run_rejects_and_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistryStore(file_path=str(Path(tmp) / "agents.json"))
            profile = registry.create_agent(
                AgentProfileCreateRequest(
                    name="confirm-agent",
                    description="test",
                    system_prompt="test",
                    task_type=TaskType.coding,
                    enabled_tools=["apply_patch"],
                    use_tool_loop=True,
                )
            )
            service = AgentService(
                chat_service=LoopChatStub(['{"action":"final","answer":"ok"}']),
                registry=registry,
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=object(),  # type: ignore[arg-type]
                verify_after_patch=False,
                max_concurrency=1,
            )
            try:
                created = service.create_run(profile.agent_id, AgentRunRequest(input="patch"))
                run_id = created.run_id
                checkpoint = json.dumps(
                    {
                        "history": [{"role": "user", "content": "patch"}],
                        "pending_tool": "apply_patch",
                        "pending_arguments": {"path": "a.txt", "content": "x", "create": True},
                        "step": 1,
                    }
                )
                with service._lock:
                    record = service._run_store.get_run(run_id)
                    assert record is not None
                    record.state = AgentRunState.awaiting_confirmation
                    record.checkpoint_json = checkpoint
                    service._run_store.put_run(record)

                rejected = service.confirm_run(run_id, approved=False)
                self.assertEqual(rejected.state, AgentRunState.failed)

                with service._lock:
                    record = service._run_store.get_run(run_id)
                    assert record is not None
                    record.state = AgentRunState.awaiting_confirmation
                    record.error = None
                    record.checkpoint_json = checkpoint
                    service._run_store.put_run(record)

                approved = service.confirm_run(run_id, approved=True)
                self.assertTrue(approved.resumed)
                self.assertEqual(approved.state, AgentRunState.queued)
            finally:
                service.stop()

    def test_confirm_run_keeps_verify_retry_counter_in_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistryStore(file_path=str(Path(tmp) / "agents.json"))
            profile = registry.create_agent(
                AgentProfileCreateRequest(
                    name="confirm-retry-counter",
                    description="test",
                    system_prompt="test",
                    task_type=TaskType.coding,
                    enabled_tools=["apply_patch"],
                    use_tool_loop=True,
                )
            )
            service = AgentService(
                chat_service=LoopChatStub(['{"action":"final","answer":"ok"}']),
                registry=registry,
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=object(),  # type: ignore[arg-type]
                verify_after_patch=False,
                max_concurrency=1,
            )
            try:
                created = service.create_run(profile.agent_id, AgentRunRequest(input="patch"))
                run_id = created.run_id
                checkpoint = json.dumps(
                    {
                        "history": [{"role": "user", "content": "patch"}],
                        "pending_tool": "apply_patch",
                        "pending_arguments": {"path": "a.txt", "content": "x", "create": True},
                        "step": 1,
                        "verify_retries_used": 1,
                    }
                )
                with service._lock:
                    record = service._run_store.get_run(run_id)
                    assert record is not None
                    record.state = AgentRunState.awaiting_confirmation
                    record.checkpoint_json = checkpoint
                    service._run_store.put_run(record)
                approved = service.confirm_run(run_id, approved=True)
                self.assertTrue(approved.resumed)
                with service._lock:
                    record = service._run_store.get_run(run_id)
                    assert record is not None
                    data = json.loads(record.checkpoint_json or "{}")
                self.assertEqual(data.get("verify_retries_used"), 1)
            finally:
                service.stop()

    def test_reindex_path_updates_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "app.py"
            target.write_text("alpha = 1\n", encoding="utf-8")
            service = CodeRetrievalService(root_path=str(root), mode="keyword")
            service.reindex()
            target.write_text("beta = 2\n", encoding="utf-8")
            service.reindex_path("app.py")
            hits = service.search("beta", limit=3)
            self.assertTrue(any("beta" in hit.content for hit in hits))


if __name__ == "__main__":
    unittest.main()
