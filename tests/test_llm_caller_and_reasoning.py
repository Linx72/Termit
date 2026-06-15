"""Tests for LLM caller and reasoning orchestrator."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from app.domain.schemas import ChatMessage
from app.services.llm_caller_service import LlmCallerService
from app.services.model_router import ModelRouter
from app.services.reasoning_orchestrator_service import ReasoningOrchestratorService


class _FakeProvider:
    name = "openai_compat"

    async def generate(self, model_name, messages, temperature, max_tokens):
        joined = " ".join(message.content for message in messages)
        return f"generated:{model_name}:{joined[:40]}"

    def list_models(self):
        return ["openai_compat:teacher"]

    async def check_health(self):
        return True, "ok"


class LlmCallerServiceTests(unittest.TestCase):
    def test_call_provider(self) -> None:
        settings = MagicMock()
        settings.fast_model = "ollama:fast"
        settings.code_model = "ollama:strong"
        settings.frontier_fallback_model = "openai_compat:frontier"
        router = ModelRouter(settings)
        service = LlmCallerService(
            providers={"openai_compat": _FakeProvider()},
            model_router=router,
        )
        text = service.call(
            "openai_compat:teacher",
            "hello",
            system="sys",
        )
        self.assertIn("generated:openai_compat:teacher", text)


class ReasoningOrchestratorTests(unittest.TestCase):
    def test_reasoning_pass(self) -> None:
        llm = MagicMock()
        llm.call.side_effect = ["draft plan", "critique bullets", "refined plan"]
        service = ReasoningOrchestratorService(
            llm_caller=llm,
            draft_model="ollama:fast",
            critic_model="openai_compat:frontier",
        )
        result = service.run_reasoning_pass(task="fix tests in app/")
        self.assertEqual(result.refined_plan, "refined plan")
        messages = service.build_plan_messages(result)
        self.assertTrue(any(message.role == "user" for message in messages))


if __name__ == "__main__":
    unittest.main()
