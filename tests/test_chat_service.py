import asyncio
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
    )
    return ModelRouter(settings)


class ChatServiceTests(unittest.TestCase):
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
        self.assertEqual(result.attempted_models, ["ollama:code", "openai_compat:code"])

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
        all_text = "".join(chunks)
        self.assertIn("event: meta", all_text)
        self.assertIn("event: token", all_text)
        self.assertIn("event: done", all_text)
        self.assertIn("attempted_models", all_text)

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


if __name__ == "__main__":
    unittest.main()
