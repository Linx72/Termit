import unittest

from app.core.config import Settings
from app.domain.schemas import TaskType
from app.services.model_router import ModelRouter


def build_settings() -> Settings:
    return Settings(
        host="0.0.0.0",
        port=8765,
        allowed_origins=["*"],
        default_model="ollama:general",
        code_model="ollama:code",
        analysis_model="ollama:analysis",
        default_fallback_model="openai_compat:general",
        code_fallback_model="openai_compat:code",
        analysis_fallback_model="openai_compat:analysis",
        ollama_base_url="http://localhost:11434",
        openai_compat_base_url="http://localhost:8001",
        openai_compat_api_key="",
        memory_backend="memory",
        memory_sqlite_path="./test_memory.db",
        memory_max_messages=40,
    )


class ModelRouterTests(unittest.TestCase):
    def test_candidate_models_for_coding(self) -> None:
        router = ModelRouter(build_settings())
        self.assertEqual(
            router.candidate_models(TaskType.coding),
            ["ollama:code", "openai_compat:code"],
        )

    def test_candidate_models_requested_model_overrides(self) -> None:
        router = ModelRouter(build_settings())
        self.assertEqual(
            router.candidate_models(TaskType.general, requested_model="ollama:custom"),
            ["ollama:custom"],
        )

    def test_candidate_models_deduplicates(self) -> None:
        settings = build_settings()
        settings = Settings(
            **{**settings.__dict__, "default_fallback_model": "ollama:general"}
        )
        router = ModelRouter(settings)
        self.assertEqual(router.candidate_models(TaskType.general), ["ollama:general"])


if __name__ == "__main__":
    unittest.main()
