from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import (
    AgentProfileCreateRequest,
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


if __name__ == "__main__":
    unittest.main()
