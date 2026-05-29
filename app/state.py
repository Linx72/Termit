from functools import lru_cache

from app.core.config import get_settings
from app.services.chat_service import ChatService
from app.services.memory_store import MemoryBackend, MemoryStore
from app.services.model_router import ModelRouter
from app.services.providers.base import BaseProvider
from app.services.providers.ollama_provider import OllamaProvider
from app.services.providers.openai_compat_provider import OpenAICompatProvider
from app.services.sqlite_memory_store import SQLiteMemoryStore
from app.services.task_service import TaskService
from app.services.tooling_service import ToolingService


@lru_cache
def _build_chat_service() -> ChatService:
    settings = get_settings()
    providers: dict[str, BaseProvider] = {
        "ollama": OllamaProvider(settings.ollama_base_url),
        "openai_compat": OpenAICompatProvider(
            settings.openai_compat_base_url,
            settings.openai_compat_api_key,
        ),
    }
    router = ModelRouter(settings)
    memory_store: MemoryBackend
    if settings.memory_backend == "sqlite":
        memory_store = SQLiteMemoryStore(
            db_path=settings.memory_sqlite_path,
            max_messages_per_session=settings.memory_max_messages,
        )
    else:
        memory_store = MemoryStore(max_messages_per_session=settings.memory_max_messages)
    return ChatService(router, providers, memory_store)


def get_chat_service() -> ChatService:
    return _build_chat_service()


@lru_cache
def _build_tooling_service() -> ToolingService:
    return ToolingService(root_path=".")


def get_tooling_service() -> ToolingService:
    return _build_tooling_service()


@lru_cache
def _build_task_service() -> TaskService:
    return TaskService(_build_tooling_service())


def get_task_service() -> TaskService:
    return _build_task_service()
