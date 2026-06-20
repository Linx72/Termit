"""vLLM OpenAI-compatible provider (ось A): быстрый local inference для coding MoE."""

from __future__ import annotations

from app.services.providers.openai_compat_provider import OpenAICompatProvider


class VllmProvider(OpenAICompatProvider):
    """OpenAI /v1/chat/completions против vLLM sidecar (PagedAttention, continuous batching)."""

    name = "vllm"

    def _strip_prefix(self, model_name: str) -> str:
        if model_name.startswith("vllm:"):
            return model_name.split(":", 1)[1]
        return super()._strip_prefix(model_name)

    def list_models(self) -> list[str]:
        return [
            "vllm:Qwen/Qwen3-Coder-Next",
            "vllm:Qwen/Qwen2.5-Coder-7B-Instruct",
        ]
