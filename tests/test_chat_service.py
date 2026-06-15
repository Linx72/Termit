import asyncio
import json
import unittest

from app.core.config import Settings
from app.domain.schemas import ChatMessage, ChatRequest, TaskType
from app.services.chat_service import ChatService
from app.services.memory_store import MemoryStore
from app.services.model_router import ModelRouter
from app.services.providers.base import BaseProvider, ProviderError


class StubProvider(BaseProvider):
    name = "stub"

    def __init__(self, response: str = "ok", fail: bool = False) -> None:
        self.response = response
        self.fail = fail

    async def generate(
        self,
        model_name: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        if self.fail:
            raise ProviderError("stub failed")
        return f"{self.response}:{model_name}"

    def list_models(self) -> list[str]:
        return ["stub:model"]

    async def check_health(self) -> tuple[bool, str]:
        return (not self.fail, "ok" if not self.fail else "failed")


class CountingProvider(StubProvider):
    def __init__(self, response: str = "ok", fail: bool = False) -> None:
        super().__init__(response=response, fail=fail)
        self.calls = 0
        self.last_messages: list[ChatMessage] = []

    async def generate(
        self,
        model_name: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        self.calls += 1
        self.last_messages = list(messages)
        return await super().generate(model_name, messages, temperature, max_tokens)


class FlakyProvider(StubProvider):
    def __init__(self, response: str = "ok", fail_attempts: int = 1) -> None:
        super().__init__(response=response, fail=False)
        self.fail_attempts = fail_attempts
        self.calls = 0

    async def generate(
        self,
        model_name: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        self.calls += 1
        if self.calls <= self.fail_attempts:
            raise ProviderError("transient failure")
        return await super().generate(model_name, messages, temperature, max_tokens)


def build_router() -> ModelRouter:
    settings = Settings(
        host="0.0.0.0",
        port=8765,
        allowed_origins=["*"],
        default_model="ollama:default",
        code_model="ollama:code",
        analysis_model="ollama:analysis",
        default_fallback_model="openai_compat:default",
        code_fallback_model="openai_compat:code",
        analysis_fallback_model="openai_compat:analysis",
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
    return ModelRouter(settings)


class ChatServiceTests(unittest.TestCase):
    @staticmethod
    def _parse_sse_chunks(chunks: list[str]) -> list[tuple[str, dict[str, object]]]:
        events: list[tuple[str, dict[str, object]]] = []
        for raw_event in "".join(chunks).split("\n\n"):
            if not raw_event.strip():
                continue
            lines = raw_event.split("\n")
            event_name = ""
            data_str = "{}"
            for line in lines:
                if line.startswith("event:"):
                    event_name = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data_str = line.split(":", 1)[1].strip()
            events.append((event_name, json.loads(data_str)))
        return events

    def test_fallback_model_is_used(self) -> None:
        service = ChatService(
            model_router=build_router(),
            providers={
                "ollama": StubProvider(fail=True),
                "openai_compat": StubProvider(response="fallback"),
            },
            memory_store=MemoryStore(),
        )
        payload = ChatRequest(message="hi", task_type=TaskType.coding)

        result = asyncio.run(service.chat(payload))

        self.assertEqual(result.provider, "openai_compat")
        self.assertEqual(result.model, "openai_compat:code")
        self.assertEqual(result.attempted_models, ["ollama:qwen2.5-coder", "ollama:code", "openai_compat:code"])

    def test_memory_is_persisted(self) -> None:
        memory = MemoryStore()
        service = ChatService(
            model_router=build_router(),
            providers={
                "ollama": StubProvider(response="primary"),
                "openai_compat": StubProvider(response="fallback"),
            },
            memory_store=memory,
        )
        payload = ChatRequest(message="first", task_type=TaskType.general, use_memory=True)

        result = asyncio.run(service.chat(payload))

        self.assertTrue(result.session_id)
        history = memory.get(result.session_id or "")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].role, "user")
        self.assertEqual(history[1].role, "assistant")

    def test_chat_stream_emits_meta_token_done(self) -> None:
        service = ChatService(
            model_router=build_router(),
            providers={
                "ollama": StubProvider(response="streamed"),
                "openai_compat": StubProvider(response="fallback"),
            },
            memory_store=MemoryStore(),
        )
        payload = ChatRequest(message="stream", task_type=TaskType.general, use_memory=False)

        async def collect() -> list[str]:
            chunks: list[str] = []
            async for chunk in service.chat_stream(payload):
                chunks.append(chunk)
            return chunks

        chunks = asyncio.run(collect())
        events = self._parse_sse_chunks(chunks)
        event_names = [name for name, _ in events]

        self.assertIn("meta", event_names)
        self.assertIn("token", event_names)
        self.assertIn("done", event_names)
        meta_payload = next(payload for name, payload in events if name == "meta")
        self.assertEqual(meta_payload["attempted_models"], ["ollama:default"])

    def test_chat_stream_preserves_special_characters(self) -> None:
        expected = 'line one\nquote: "test" and slash \\'
        service = ChatService(
            model_router=build_router(),
            providers={
                "ollama": StubProvider(response=expected),
                "openai_compat": StubProvider(response="fallback"),
            },
            memory_store=MemoryStore(),
        )
        payload = ChatRequest(message="stream special", task_type=TaskType.general, use_memory=False)

        async def collect() -> list[str]:
            chunks: list[str] = []
            async for chunk in service.chat_stream(payload):
                chunks.append(chunk)
            return chunks

        events = self._parse_sse_chunks(asyncio.run(collect()))
        rebuilt = "".join(
            payload.get("text", "")
            for name, payload in events
            if name == "token"
        )
        self.assertEqual(rebuilt, f"{expected}:ollama:default")

    def test_export_session_markdown(self) -> None:
        memory = MemoryStore()
        memory.append("s-exp", ChatMessage(role="user", content="hello"))
        memory.append("s-exp", ChatMessage(role="assistant", content="world"))
        service = ChatService(
            model_router=build_router(),
            providers={
                "ollama": StubProvider(response="ok"),
                "openai_compat": StubProvider(response="fallback"),
            },
            memory_store=memory,
        )

        content, count = service.export_session_markdown("s-exp")

        self.assertEqual(count, 2)
        self.assertIn("# Session s-exp", content)
        self.assertIn("## 1. User", content)
        self.assertIn("## 2. Assistant", content)

    def test_export_session_txt_and_json(self) -> None:
        memory = MemoryStore()
        memory.append("s-exp2", ChatMessage(role="user", content="alpha"))
        memory.append("s-exp2", ChatMessage(role="assistant", content="beta"))
        service = ChatService(
            model_router=build_router(),
            providers={
                "ollama": StubProvider(response="ok"),
                "openai_compat": StubProvider(response="fallback"),
            },
            memory_store=memory,
        )

        txt_content, txt_count = service.export_session_txt("s-exp2")
        json_content, json_count = service.export_session_json("s-exp2")

        self.assertEqual(txt_count, 2)
        self.assertIn("[user] alpha", txt_content)
        self.assertIn("[assistant] beta", txt_content)
        self.assertEqual(json_count, 2)
        self.assertIn('"session_id": "s-exp2"', json_content)
        self.assertIn('"role": "assistant"', json_content)

    def test_non_memory_requests_use_cache(self) -> None:
        primary = CountingProvider(response="cached")
        service = ChatService(
            model_router=build_router(),
            providers={
                "ollama": primary,
                "openai_compat": StubProvider(response="fallback"),
            },
            memory_store=MemoryStore(),
            cache_ttl_seconds=300,
        )
        payload = ChatRequest(message="repeat", task_type=TaskType.general, use_memory=False)

        first = asyncio.run(service.chat(payload))
        second = asyncio.run(service.chat(payload))

        self.assertEqual(first.response, second.response)
        self.assertEqual(primary.calls, 1)

    def test_context_compaction_limits_messages(self) -> None:
        primary = CountingProvider(response="compacted")
        service = ChatService(
            model_router=build_router(),
            providers={
                "ollama": primary,
                "openai_compat": StubProvider(response="fallback"),
            },
            memory_store=MemoryStore(),
            cache_ttl_seconds=0,
        )
        long_history = [
            ChatMessage(role="user", content=f"msg-{index}-" + ("x" * 900))
            for index in range(30)
        ]
        payload = ChatRequest(
            message="current",
            task_type=TaskType.general,
            history=long_history,
            use_memory=False,
        )

        asyncio.run(service.chat(payload))

        self.assertLessEqual(len(primary.last_messages), 22)
        self.assertEqual(primary.last_messages[-1].content, "current")
        self.assertTrue(any("[Context compaction]" in item.content for item in primary.last_messages))

    def test_retrieval_injects_workspace_context(self) -> None:
        from app.services.code_retrieval_service import CodeRetrievalService

        primary = CountingProvider(response="with-context")
        retrieval = CodeRetrievalService(root_path=".")
        retrieval.reindex()
        service = ChatService(
            model_router=build_router(),
            providers={
                "ollama": primary,
                "openai_compat": StubProvider(response="fallback"),
            },
            memory_store=MemoryStore(),
            cache_ttl_seconds=0,
            code_retrieval=retrieval,
            retrieval_enabled=True,
        )
        payload = ChatRequest(
            message="How does ChatService compact context?",
            task_type=TaskType.coding,
            use_memory=False,
            use_retrieval=True,
            retrieval_limit=3,
            retrieval_path_prefix="app/services/",
        )
        response = asyncio.run(service.chat(payload))
        self.assertGreaterEqual(response.retrieval_hits, 1)
        self.assertTrue(
            any(
                "[Retrieved codebase context]" in item.content
                for item in primary.last_messages
            )
        )

    def test_retry_with_backoff_recovers_from_transient_error(self) -> None:
        flaky = FlakyProvider(response="recovered", fail_attempts=1)
        service = ChatService(
            model_router=build_router(),
            providers={
                "ollama": flaky,
                "openai_compat": StubProvider(response="fallback"),
            },
            memory_store=MemoryStore(),
            provider_retry_attempts=2,
            provider_retry_backoff_ms=1,
        )
        payload = ChatRequest(message="retry please", task_type=TaskType.general, use_memory=False)

        result = asyncio.run(service.chat(payload))

        self.assertEqual(result.provider, "ollama")
        self.assertEqual(flaky.calls, 2)


if __name__ == "__main__":
    unittest.main()
