"""Фабрика LLM-провайдеров Termit (Ollama, cloud compat, vLLM sidecar)."""

from __future__ import annotations

from app.core.config import Settings
from app.services.providers.base import BaseProvider
from app.services.providers.ollama_provider import OllamaProvider
from app.services.providers.openai_compat_provider import OpenAICompatProvider
from app.services.providers.vllm_provider import VllmProvider


def build_llm_providers(settings: Settings) -> dict[str, BaseProvider]:
    """Собрать runtime providers; vLLM всегда регистрируется для prefix vllm:."""
    providers: dict[str, BaseProvider] = {
        "ollama": OllamaProvider(settings.ollama_base_url),
        "openai_compat": OpenAICompatProvider(
            settings.openai_compat_base_url,
            settings.openai_compat_api_key,
        ),
        "vllm": VllmProvider(settings.vllm_base_url, settings.vllm_api_key),
    }
    return providers
