from __future__ import annotations

import unittest

from app.services.agent_loop_service import _model_supports_native_tool_calls
from app.services.providers.factory import build_llm_providers
from app.services.providers.vllm_provider import VllmProvider


class VllmProviderTests(unittest.IsolatedAsyncioTestCase):
    def test_strip_vllm_prefix(self) -> None:
        provider = VllmProvider("http://127.0.0.1:8000", "")
        self.assertEqual(
            provider._strip_prefix("vllm:Qwen/Qwen3-Coder-Next"),
            "Qwen/Qwen3-Coder-Next",
        )

    def test_model_router_provider_vllm(self) -> None:
        from app.services.model_router import ModelRouter

        self.assertEqual(
            ModelRouter.provider_for_model("vllm:Qwen/Qwen3-Coder-Next"),
            "vllm",
        )

    def test_native_tool_calls_supports_vllm(self) -> None:
        self.assertTrue(_model_supports_native_tool_calls("vllm:Qwen/Qwen3-Coder-Next"))

    def test_factory_registers_vllm(self) -> None:
        from app.core.config import get_settings

        providers = build_llm_providers(get_settings())
        self.assertIn("vllm", providers)
        self.assertIsInstance(providers["vllm"], VllmProvider)

    async def test_vllm_health_check_unreachable(self) -> None:
        provider = VllmProvider("http://127.0.0.1:59999", "")
        ok, detail = await provider.check_health()
        self.assertFalse(ok)
        self.assertTrue(detail)


if __name__ == "__main__":
    unittest.main()
