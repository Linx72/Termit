from abc import ABC, abstractmethod
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
