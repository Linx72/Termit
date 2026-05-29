from abc import ABC, abstractmethod

from app.domain.schemas import ChatMessage


class ProviderError(RuntimeError):
    pass


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
