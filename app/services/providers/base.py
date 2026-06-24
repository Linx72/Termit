from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Optional

from app.domain.schemas import ChatMessage


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderToolCall:
    id: str
    name: str
    arguments: dict[str, object]


@dataclass
class ProviderToolResponse:
    content: str = ""
    tool_calls: list[ProviderToolCall] = field(default_factory=list)
    finish_reason: str = ""


@dataclass
class ProviderStreamChunk:
    """Один чанк стриминга от провайдера."""
    token: str = ""            # Инкрементальный текстовый токен
    reasoning: str = ""        # Reasoning-токен (для DeepSeek R1 и др.)
    tool_call_delta: Optional[ProviderToolCall] = None  # Частичный tool_call (аргументы достраиваются)
    finish_reason: str = ""    # stop / length / tool_calls
    is_done: bool = False      # Поток завершён


class BaseProvider(ABC):
    name: str

    @abstractmethod
    async def generate(
        self,
        model_name: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def check_health(self) -> tuple[bool, str]:
        raise NotImplementedError

    async def generate_stream(
        self,
        model_name: str,
        messages: list[ChatMessage],
        temperature: float,
        max_tokens: int,
        tools: Optional[list[dict[str, object]]] = None,
    ) -> AsyncIterator[ProviderStreamChunk]:
        """
        Реальный SSE-стриминг токенов от LLM-провайдера.
        
        Если провайдер не поддерживает нативный стриминг, реализация по умолчанию
        вызывает generate() и эмулирует чанки (с сохранением обратной совместимости).
        """
        text = await self.generate(
            model_name=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # Эмуляция: отдаём по одному слову для плавности
        words = text.split(" ")
        for i, word in enumerate(words):
            suffix = " " if i < len(words) - 1 else ""
            yield ProviderStreamChunk(token=word + suffix)
        yield ProviderStreamChunk(is_done=True, finish_reason="stop")
