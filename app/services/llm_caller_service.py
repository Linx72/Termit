"""Sync LLM caller for teacher distillation, eval judge, and offline scripts."""

from __future__ import annotations

import asyncio
from typing import Optional

from app.domain.schemas import ChatMessage
from app.services.model_router import ModelRouter
from app.services.providers.base import BaseProvider, ProviderError


class LlmCallerService:
    def __init__(
        self,
        *,
        providers: dict[str, BaseProvider],
        model_router: ModelRouter,
        default_temperature: float = 0.2,
        default_max_tokens: int = 2048,
    ) -> None:
        self._providers = providers
        self._model_router = model_router
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens

    def call(
        self,
        model_name: str,
        prompt: str,
        *,
        system: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        messages: list[ChatMessage] = []
        if system.strip():
            messages.append(ChatMessage(role="system", content=system.strip()))
        messages.append(ChatMessage(role="user", content=prompt))
        return asyncio.run(
            self._generate(
                model_name=model_name,
                messages=messages,
                temperature=temperature if temperature is not None else self._default_temperature,
                max_tokens=max_tokens if max_tokens is not None else self._default_max_tokens,
            )
        )

    async def _generate(
        self,
        *,
        model_name: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        provider_name = self._model_router.provider_for_model(model_name)
        provider = self._providers.get(provider_name)
        if provider is None:
            raise ProviderError(f"Provider not configured: {provider_name}")
        return await provider.generate(
            model_name=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def is_model_available(self, model_name: str) -> bool:
        provider_name = self._model_router.provider_for_model(model_name)
        return provider_name in self._providers
