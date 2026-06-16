from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import (
    AgentProfileCreateRequest,
    ExecuteCommandResponse,
    AgentRunRequest,
    AgentRunState,
    ChatResponse,
    ReadFileRequest,
    TaskType,
    WebAutomationResponse,
    WebEvidence,
)
from app.services.agent_registry_store import AgentRegistryStore
from app.services.agent_run_store import InMemoryAgentRunStore
from app.services.agent_service import (
    AgentNotFoundError,
    AgentPermissionError,
    AgentRunNotFoundError,
    AgentService,
)
from app.services.tooling_service import ToolingService


class StubChatService:
    def __init__(self, fail_attempts: int = 0) -> None:
        self.last_request = None
        self._fail_attempts = fail_attempts
        self.calls = 0

    async def chat(self, payload):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.calls <= self._fail_attempts:
            raise RuntimeError("transient chat failure")
        self.last_request = payload
        model = payload.model or "ollama:default"
        return ChatResponse(
            provider="ollama",
            model=model,
            task_type=payload.task_type,
            session_id=payload.session_id or "sess-test",
            history_size=len(payload.history) + 1,
            attempted_models=[model],
            response="agent response",
        )


class SlowChatService(StubChatService):
    async def chat(self, payload):  # type: ignore[no-untyped-def]
        await asyncio.sleep(0.2)
        return await super().chat(payload)


class HangingChatService(StubChatService):
    async def chat(self, payload):  # type: ignore[no-untyped-def]
        await asyncio.sleep(15)
        return await super().chat(payload)


class StubBrowserWorkflow:
    def run(self, payload):  # type: ignore[no-untyped-def]
        return WebAutomationResponse(
            objective=payload.objective,
            success=True,
            blocker_detected=False,
            steps=["Action: navigate", "Workflow finished with collected evidence."],
            evidence=WebEvidence(
                requested_url=payload.url,
                final_url=payload.url,
                status_code=200,
                title="Example",
                links=[],
                snapshot_excerpt="<html></html>",
            ),
            duration_ms=5,
        )


class AgentServiceTests(unittest.TestCase):
    @staticmethod
    def _build_service(
        tmp: str,
        chat: StubChatService | None = None,
        **kwargs,
    ) -> AgentService:
        return AgentService(
            chat_service=chat or StubChatService(),
            registry=AgentRegistryStore(file_path=str(Path(tmp) / "agents.json")),
            run_store=InMemoryAgentRunStore(),
            tooling=ToolingService(root_path="."),
            browser_workflow=StubBrowserWorkflow(),
            max_concurrency=kwargs.get("max_concurrency", 1),
            max_queue_size=kwargs.get("max_queue_size", 10),
            run_max_attempts=kwargs.get("run_max_attempts", 3),
            run_retry_backoff_ms=kwargs.get("run_retry_backoff_ms", 1),
            run_timeout_seconds=kwargs.get("run_timeout_seconds", 180),
            queue_stuck_timeout_seconds=kwargs.get("queue_stuck_timeout_seconds", 120),
            max_events_per_run=kwargs.get("max_events_per_run", 500),
            max_response_chars=kwargs.get("max_response_chars", 12000),
            retention_days=kwargs.get("retention_days", 14),
        )

    def test_create_and_run_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            chat = StubChatService()
            service = self._build_service(tmp, chat=chat)

            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Code Assistant",
                    description="Local coding helper",
                    system_prompt="You are a strict local code agent.",
                    task_type=TaskType.coding,
                    model="ollama:qwen2.5-coder",
                    use_memory=True,
                    use_retrieval=False,
                )
            )
            result = asyncio.run(service.run_agent(agent.agent_id, AgentRunRequest(input="Write tests")))

            self.assertEqual(result.agent_name, "Code Assistant")
            self.assertEqual(result.model, "ollama:qwen2.5-coder")
            self.assertEqual(result.task_type, TaskType.coding)
            self.assertIsNotNone(chat.last_request)
            self.assertEqual(chat.last_request.history[0].role, "system")
            self.assertIn("strict local code agent", chat.last_request.history[0].content)

    def test_missing_agent_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(tmp)
            with self.assertRaises(AgentNotFoundError):
                asyncio.run(service.run_agent("agt_missing", AgentRunRequest(input="Hello")))

    def test_background_run_completes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(tmp)
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Queue Agent",
                    description="Background runner",
                    system_prompt="Process task in background.",
                    task_type=TaskType.general,
                    enabled_tools=["list_files"],
                )
            )
            queued = service.create_run(agent.agent_id, AgentRunRequest(input="Do queue work"))
            self.assertEqual(queued.state.value, "queued")

            # Poll briefly until worker flips state.
            final_state = ""
            for _ in range(30):
                record = service.get_run(queued.run_id)
                final_state = record.state.value
                if final_state in {"completed", "failed"}:
                    break
                asyncio.run(asyncio.sleep(0.02))

            self.assertEqual(final_state, "completed")

    def test_background_run_timeout_transitions_to_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(
                tmp,
                chat=HangingChatService(),
                run_max_attempts=1,
                run_retry_backoff_ms=1,
                run_timeout_seconds=10,
            )
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Timeout Agent",
                    description="timeout behavior",
                    system_prompt="This should timeout.",
                    task_type=TaskType.general,
                )
            )
            queued = service.create_run(agent.agent_id, AgentRunRequest(input="hang"))
            final = None
            for _ in range(520):
                record = service.get_run(queued.run_id)
                if record.state in {AgentRunState.completed, AgentRunState.failed, AgentRunState.cancelled}:
                    final = record
                    break
                asyncio.run(asyncio.sleep(0.05))
            self.assertIsNotNone(final)
            assert final is not None
            self.assertEqual(final.state, AgentRunState.failed)
            self.assertEqual(final.failure_class, "run_timeout")
            self.assertIn("Run exceeded timeout", final.error or "")

    def test_cancel_running_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(tmp, chat=SlowChatService())
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Cancelable Agent",
                    description="Background runner",
                    system_prompt="Process task in background.",
                    task_type=TaskType.general,
                    enabled_tools=["list_files"],
                )
            )
            queued = service.create_run(agent.agent_id, AgentRunRequest(input="Do queue work"))
            for _ in range(50):
                record = service.get_run(queued.run_id)
                if record.state == AgentRunState.running:
                    break
                asyncio.run(asyncio.sleep(0.01))
            cancelled = service.cancel_run(queued.run_id)
            self.assertTrue(cancelled.cancelled, msg=f"state={cancelled.state}")
            self.assertEqual(cancelled.state, AgentRunState.cancelled)

    def test_tool_permissions_block_not_enabled_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(tmp)
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="No Tools",
                    description="No tool permissions",
                    system_prompt="Chat only.",
                    task_type=TaskType.general,
                    enabled_tools=[],
                )
            )
            with self.assertRaises(AgentPermissionError):
                service.read_file_as_agent(agent.agent_id, ReadFileRequest(path="README.md"))

    def test_online_run_uses_web_automation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(tmp)
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Online Agent",
                    description="online enabled",
                    system_prompt="Can browse web safely.",
                    task_type=TaskType.general,
                    allow_online=True,
                    enabled_tools=["web_automation"],
                )
            )
            result = asyncio.run(
                service.run_agent(
                    agent.agent_id,
                    AgentRunRequest(
                        input="Collect homepage evidence",
                        online_url="https://example.com",
                    ),
                )
            )
            self.assertEqual(result.provider, "automation")
            self.assertEqual(result.model, "web_automation")
            self.assertIn("Online objective", result.response)

    def test_background_run_retries_and_records_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            flaky = StubChatService(fail_attempts=1)
            service = self._build_service(tmp, chat=flaky)
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Retry Agent",
                    description="retry behavior",
                    system_prompt="Retry transient failures.",
                    task_type=TaskType.general,
                )
            )
            queued = service.create_run(agent.agent_id, AgentRunRequest(input="retry this run"))
            final = None
            for _ in range(50):
                record = service.get_run(queued.run_id)
                if record.state.value in {"completed", "failed"}:
                    final = record
                    break
                asyncio.run(asyncio.sleep(0.02))
            self.assertIsNotNone(final)
            assert final is not None
            self.assertEqual(final.state.value, "completed")
            self.assertGreaterEqual(final.attempts, 2)
            events = service.get_run_events(queued.run_id)
            event_types = [item.event_type for item in events]
            self.assertIn("run_retry_scheduled", event_types)
            self.assertIn("run_completed", event_types)

    def test_queue_metrics_and_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(tmp)
            metrics = service.queue_metrics()
            self.assertEqual(metrics["worker_count"], 1)
            self.assertEqual(metrics["queue_capacity"], 10)
            self.assertIn("stale_queued_runs", metrics)
            self.assertIn("stale_running_runs", metrics)
            self.assertIn("lifecycle_stale_total", metrics)
            self.assertIn("lifecycle_terminal_runs_total", metrics)
            self.assertIn("lifecycle_completed_runs_total", metrics)
            self.assertIn("lifecycle_timeout_runs_total", metrics)
            self.assertIn("lifecycle_completion_rate", metrics)
            self.assertIn("queue_stuck_timeout_seconds", metrics)

            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Cleanup Agent",
                    description="cleanup behavior",
                    system_prompt="Cleanup stale runs.",
                    task_type=TaskType.general,
                )
            )
            queued = service.create_run(agent.agent_id, AgentRunRequest(input="complete run"))
            for _ in range(40):
                record = service.get_run(queued.run_id)
                if record.state in {AgentRunState.completed, AgentRunState.failed}:
                    break
                asyncio.run(asyncio.sleep(0.02))

            stale = service.get_run(queued.run_id)
            stale.updated_at = "2000-01-01T00:00:00+00:00"
            stale.state = AgentRunState.completed
            service._run_store.put_run(stale)  # type: ignore[attr-defined]

            dry = service.cleanup_runs(retention_days=1, dry_run=True)
            self.assertEqual(dry["deleted_runs"], 1)
            self.assertGreaterEqual(dry["remaining_runs"], 1)
            applied = service.cleanup_runs(retention_days=1, dry_run=False)
            self.assertEqual(applied["deleted_runs"], 1)
            with self.assertRaises(AgentRunNotFoundError):
                service.get_run(queued.run_id)

    def test_queue_metrics_detect_stale_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(tmp, queue_stuck_timeout_seconds=1)
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Metrics Agent",
                    description="stale metrics",
                    system_prompt="noop",
                    task_type=TaskType.general,
                )
            )
            stale_queued = service.create_run(agent.agent_id, AgentRunRequest(input="queued stale"))
            stale_running = service.create_run(agent.agent_id, AgentRunRequest(input="running stale"))
            queued_record = service.get_run(stale_queued.run_id)
            running_record = service.get_run(stale_running.run_id)
            queued_record.updated_at = "2000-01-01T00:00:00+00:00"
            running_record.state = AgentRunState.running
            running_record.updated_at = "2000-01-01T00:00:00+00:00"
            service._run_store.put_run(queued_record)  # type: ignore[attr-defined]
            service._run_store.put_run(running_record)  # type: ignore[attr-defined]
            metrics = service.queue_metrics()
            self.assertGreaterEqual(metrics["stale_queued_runs"], 1)
            self.assertGreaterEqual(metrics["stale_running_runs"], 1)
            self.assertGreaterEqual(metrics["lifecycle_stale_total"], 2)

    def test_cleanup_stale_active_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(tmp)
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Stale Agent",
                    description="stale run cleanup",
                    system_prompt="Do work.",
                    task_type=TaskType.general,
                )
            )
            queued = service.create_run(agent.agent_id, AgentRunRequest(input="stale"))
            run = service.get_run(queued.run_id)
            run.state = AgentRunState.running
            run.updated_at = "2000-01-01T00:00:00+00:00"
            service._run_store.put_run(run)  # type: ignore[attr-defined]
            result = service.cleanup_stale_active_runs(
                stale_before_iso="2000-01-02T00:00:00+00:00",
                dry_run=False,
            )
            self.assertEqual(result["cancelled_runs"], 1)
            updated = service.get_run(queued.run_id)
            self.assertEqual(updated.state, AgentRunState.cancelled)

    def test_event_history_trimmed_to_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            flaky = StubChatService(fail_attempts=2)
            service = self._build_service(
                tmp,
                chat=flaky,
                run_max_attempts=3,
                max_events_per_run=3,
            )
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Trim Agent",
                    description="event trim",
                    system_prompt="Generate enough events to trim.",
                    task_type=TaskType.general,
                )
            )
            queued = service.create_run(agent.agent_id, AgentRunRequest(input="trim events"))
            for _ in range(60):
                record = service.get_run(queued.run_id)
                if record.state in {AgentRunState.completed, AgentRunState.failed}:
                    break
                asyncio.run(asyncio.sleep(0.02))
            events = service.get_run_events(queued.run_id, limit=100)
            self.assertLessEqual(len(events), 3)

    def test_verify_failure_schedules_run_retry(self) -> None:
        class NativeLoopChatService(StubChatService):
            def __init__(self) -> None:
                super().__init__()
                self._responses = [
                    '{"action":"tool","tool":"execute_command","arguments":{"command":"echo ok","path":".","dry_run":false,"confirmed":true}}',
                    '{"action":"final","answer":"first final"}',
                    '{"action":"final","answer":"second final"}',
                ]

            async def chat(self, payload):  # type: ignore[no-untyped-def]
                text = self._responses.pop(0)
                model = payload.model or "ollama:default"
                return ChatResponse(
                    provider="ollama",
                    model=model,
                    task_type=payload.task_type,
                    session_id=payload.session_id or "sess-test",
                    history_size=len(payload.history) + 1,
                    attempted_models=[model],
                    response=text,
                )

        with tempfile.TemporaryDirectory() as tmp:
            service = AgentService(
                chat_service=NativeLoopChatService(),
                registry=AgentRegistryStore(file_path=str(Path(tmp) / "agents.json")),
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=StubBrowserWorkflow(),
                verify_after_patch=True,
                verify_cmd="echo verify",
                verify_max_retries=1,
                max_concurrency=1,
            )
            original_execute = service._tooling.execute_command  # type: ignore[attr-defined]
            verify_calls = {"count": 0}

            def execute_with_verify_flake(payload):  # type: ignore[no-untyped-def]
                if payload.command == "echo verify":
                    verify_calls["count"] += 1
                    if verify_calls["count"] == 1:
                        return ExecuteCommandResponse(
                            command=payload.command,
                            path=payload.path,
                            dry_run=False,
                            confirmed=True,
                            executed=True,
                            exit_code=1,
                            stdout="",
                            stderr="verify failed",
                        )
                    return ExecuteCommandResponse(
                        command=payload.command,
                        path=payload.path,
                        dry_run=False,
                        confirmed=True,
                        executed=True,
                        exit_code=0,
                        stdout="verify ok",
                        stderr="",
                    )
                return original_execute(payload)

            service._tooling.execute_command = execute_with_verify_flake  # type: ignore[attr-defined]
            agent = service.create_agent(
                AgentProfileCreateRequest(
                    name="Verify Events",
                    description="verify events",
                    system_prompt="test",
                    task_type=TaskType.coding,
                    enabled_tools=["execute_command"],
                    use_tool_loop=True,
                )
            )
            queued = service.create_run(agent.agent_id, AgentRunRequest(input="verify loop"))
            final = None
            for _ in range(80):
                record = service.get_run(queued.run_id)
                if record.state in {AgentRunState.completed, AgentRunState.failed}:
                    final = record
                    break
                asyncio.run(asyncio.sleep(0.02))
            self.assertIsNotNone(final)
            assert final is not None
            self.assertEqual(final.state, AgentRunState.completed)
            events = service.get_run_events(queued.run_id, limit=200)
            event_types = [event.event_type for event in events]
            self.assertIn("run_retry_scheduled", event_types)
            self.assertIn("run_completed", event_types)

    def test_worker_lifecycle_stop_and_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(tmp, max_concurrency=2)
            before = service.queue_metrics()
            self.assertGreaterEqual(before["alive_workers"], 1)
            service.stop()
            stopped = service.queue_metrics()
            self.assertEqual(stopped["alive_workers"], 0)
            service.start()
            restarted = service.queue_metrics()
            self.assertGreaterEqual(restarted["alive_workers"], 1)

    def test_invoke_loop_tool_auto_confirms_apply_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistryStore(file_path=str(Path(tmp) / "agents.json"))
            created = registry.create_agent(
                AgentProfileCreateRequest(
                    name="Loop",
                    description="",
                    system_prompt="test",
                    task_type=TaskType.coding,
                    enabled_tools=["apply_patch"],
                    use_tool_loop=True,
                )
            )
            service = AgentService(
                chat_service=StubChatService(),
                registry=registry,
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=StubBrowserWorkflow(),
                max_concurrency=1,
                verify_after_patch=False,
            )
            target = Path(tmp) / "sample.txt"
            observation, _side_effects = service._invoke_loop_tool(
                created.agent_id,
                created,
                "apply_patch",
                {"path": "sample.txt", "content": "hello", "create": True},
                auto_confirm_risky_tools=True,
                verify_after_patch=False,
            )
            self.assertTrue(target.is_file())
            self.assertIn('"applied": true', observation.lower())

    def test_spawn_agent_is_async_and_sets_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistryStore(file_path=str(Path(tmp) / "agents.json"))
            created = registry.create_agent(
                AgentProfileCreateRequest(
                    name="Parent Agent",
                    description="",
                    system_prompt="test",
                    task_type=TaskType.coding,
                    enabled_tools=["spawn_agent"],
                    use_tool_loop=True,
                )
            )
            service = AgentService(
                chat_service=StubChatService(),
                registry=registry,
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=StubBrowserWorkflow(),
                max_concurrency=1,
                verify_after_patch=False,
            )
            observation, side_effects = service._invoke_loop_tool(
                created.agent_id,
                created,
                "spawn_agent",
                {"task": "child task"},
                run_id="run_parent_1",
            )
            payload = json.loads(observation)
            self.assertEqual(payload["state"], "queued")
            child_run_id = payload["run_id"]
            self.assertTrue(any("child_run_id=" in item[1] for item in side_effects))
            self.assertTrue(any(item[0] == "spawn_agent_child_event" for item in side_effects))
            child_run = service.get_run(child_run_id)
            self.assertEqual(child_run.parent_run_id, "run_parent_1")
            children = service.list_child_runs("run_parent_1")
            self.assertEqual(children.total, 1)
            self.assertEqual(children.runs[0].run_id, child_run_id)
            synthetic_parent = service.create_run(created.agent_id, AgentRunRequest(input="parent for timeline"))
            service._invoke_loop_tool(
                created.agent_id,
                created,
                "spawn_agent",
                {"task": "child for timeline"},
                run_id=synthetic_parent.run_id,
            )
            events = service.get_run_events(synthetic_parent.run_id, limit=200)
            self.assertTrue(any(event.event_type == "spawn_agent_child_event" for event in events))

    def test_mcp_invoke_respects_allowed_servers(self) -> None:
        class StubMcp:
            def invoke_tool(self, server_id: str, tool_name: str, arguments: dict[str, object]) -> str:
                return json.dumps({"server_id": server_id, "tool": tool_name, "arguments": arguments})

        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistryStore(file_path=str(Path(tmp) / "agents.json"))
            created = registry.create_agent(
                AgentProfileCreateRequest(
                    name="Mcp Agent",
                    description="",
                    system_prompt="test",
                    task_type=TaskType.coding,
                    enabled_tools=["mcp_invoke"],
                    allowed_mcp_servers=["allowed-server"],
                    use_tool_loop=True,
                )
            )
            service = AgentService(
                chat_service=StubChatService(),
                registry=registry,
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=StubBrowserWorkflow(),
                mcp_registry=StubMcp(),  # type: ignore[arg-type]
                max_concurrency=1,
                verify_after_patch=False,
            )
            allowed, _ = service._invoke_loop_tool(
                created.agent_id,
                created,
                "mcp_invoke",
                {"server_id": "allowed-server", "tool_name": "ping", "arguments": {"x": 1}},
            )
            self.assertIn('"tool": "ping"', allowed)
            with self.assertRaises(AgentPermissionError):
                service._invoke_loop_tool(
                    created.agent_id,
                    created,
                    "mcp_invoke",
                    {"server_id": "blocked-server", "tool_name": "ping", "arguments": {}},
                )

    def test_mcp_invoke_respects_allowed_tools(self) -> None:
        class StubMcp:
            def invoke_tool(self, server_id: str, tool_name: str, arguments: dict[str, object]) -> str:
                return json.dumps({"server_id": server_id, "tool": tool_name, "arguments": arguments})

        with tempfile.TemporaryDirectory() as tmp:
            registry = AgentRegistryStore(file_path=str(Path(tmp) / "agents.json"))
            created = registry.create_agent(
                AgentProfileCreateRequest(
                    name="Mcp Tool Agent",
                    description="",
                    system_prompt="test",
                    task_type=TaskType.coding,
                    enabled_tools=["mcp_invoke"],
                    allowed_mcp_servers=["allowed-server"],
                    allowed_mcp_tools=["ping"],
                    use_tool_loop=True,
                )
            )
            service = AgentService(
                chat_service=StubChatService(),
                registry=registry,
                run_store=InMemoryAgentRunStore(),
                tooling=ToolingService(root_path=tmp),
                browser_workflow=StubBrowserWorkflow(),
                mcp_registry=StubMcp(),  # type: ignore[arg-type]
                max_concurrency=1,
                verify_after_patch=False,
            )
            allowed, _ = service._invoke_loop_tool(
                created.agent_id,
                created,
                "mcp_invoke",
                {"server_id": "allowed-server", "tool_name": "ping", "arguments": {"x": 1}},
            )
            self.assertIn('"tool": "ping"', allowed)
            with self.assertRaises(AgentPermissionError):
                service._invoke_loop_tool(
                    created.agent_id,
                    created,
                    "mcp_invoke",
                    {"server_id": "allowed-server", "tool_name": "delete", "arguments": {}},
                )


class AgentPolicyFallbackTests(unittest.TestCase):
    def test_apply_policy_fallback_switches_to_plan_and_strict(self) -> None:
        payload = AgentRunRequest(
            input="Fix flaky test",
            policy_preset="autopilot",
            run_mode="agent",
            auto_confirm_risky_tools=True,
        )
        updated = AgentService._apply_policy_fallback(payload, "tool_error")
        self.assertEqual(updated.run_mode, "plan")
        self.assertEqual(updated.policy_preset, "strict")
        self.assertFalse(updated.auto_confirm_risky_tools)
        self.assertIn("[Policy fallback]", updated.input)

    def test_apply_policy_fallback_skips_external_errors(self) -> None:
        payload = AgentRunRequest(input="Fix bug", run_mode="agent")
        updated = AgentService._apply_policy_fallback(payload, "run_timeout")
        self.assertEqual(updated.model_dump(), payload.model_dump())


if __name__ == "__main__":
    unittest.main()
