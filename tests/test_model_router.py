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
        teacher_model="ollama:teacher",
        teacher_fallback_model="openai_compat:teacher",
        ollama_base_url="http://localhost:11434",
        openai_compat_base_url="http://localhost:8001",
        openai_compat_api_key="",
        memory_backend="memory",
        memory_sqlite_path="./test_memory.db",
        memory_max_messages=40,
        auth_enabled=False,
        api_keys={},
        quota_sqlite_path="./test_quota.db",
        default_daily_quota=1000,
        default_api_role="operator",
        feedback_file_path="./data/feedback.jsonl",
        circuit_failure_threshold=3,
        circuit_cooldown_seconds=60,
        eval_scenarios_path="./data/eval_scenarios.json",
        task_backend="memory",
        task_sqlite_path="./test_tasks.db",
        agent_registry_file_path="./data/agents.test.json",
    )


class ModelRouterTests(unittest.TestCase):
    def test_candidate_models_for_coding(self) -> None:
        router = ModelRouter(build_settings())
        self.assertEqual(
            router.candidate_models(TaskType.coding),
            ["ollama:qwen2.5-coder", "ollama:code", "openai_compat:code"],
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

    def test_high_complexity_general_prefers_analysis_models(self) -> None:
        router = ModelRouter(build_settings())
        models = router.candidate_models(
            TaskType.general,
            message="Need architecture and security migration plan across services",
            history=[],
        )
        self.assertEqual(
            models,
            [
                "ollama:analysis",
                "ollama:general",
                "openai_compat:analysis",
                "openai_compat:general",
            ],
        )

    def test_high_complexity_detected_for_russian_markers(self) -> None:
        router = ModelRouter(build_settings())
        models = router.candidate_models(
            TaskType.general,
            message="Нужен архитектурный рефактор и план по безопасности",
            history=[],
        )
        self.assertEqual(
            models,
            [
                "ollama:analysis",
                "ollama:general",
                "openai_compat:analysis",
                "openai_compat:general",
            ],
        )

    def test_low_complexity_prefers_fast_model(self) -> None:
        router = ModelRouter(build_settings())
        models = router.candidate_models(TaskType.coding, message="fix typo")
        self.assertEqual(models[0], "ollama:qwen2.5-coder")

    def test_high_complexity_includes_frontier_fallback(self) -> None:
        settings = build_settings()
        settings = Settings(
            **{
                **settings.__dict__,
                "frontier_fallback_model": "openai_compat:deepseek-ai/DeepSeek-V4-Pro",
            }
        )
        router = ModelRouter(settings)
        models = router.candidate_models(
            TaskType.coding,
            message="refactor architecture across multiple services with migration plan",
        )
        self.assertIn("openai_compat:deepseek-ai/DeepSeek-V4-Pro", models)

    def test_high_complexity_includes_frontier_chain(self) -> None:
        settings = build_settings()
        settings = Settings(
            **{
                **settings.__dict__,
                "frontier_fallback_model": "openai_compat:deepseek-ai/DeepSeek-V4-Pro",
            }
        )
        router = ModelRouter(settings)
        models = router.candidate_models(
            TaskType.coding,
            message="refactor architecture across multiple services with migration plan",
        )
        self.assertIn("openai_compat:deepseek-ai/DeepSeek-V4-Pro", models)
        self.assertIn("openai_compat:deepseek-ai/DeepSeek-V4-Flash", models)
        self.assertIn("openai_compat:deepseek-ai/DeepSeek-V3", models)

    def test_routing_tiers_exposes_frontier_chain(self) -> None:
        router = ModelRouter(build_settings())
        tiers = router.routing_tiers()
        self.assertIn("frontier_chain", tiers)
        self.assertIn("DeepSeek-V4-Pro", tiers["frontier_chain"])

    def test_cost_aware_routing_prefers_cheaper_model_for_low_complexity(self) -> None:
        settings = Settings(
            **{
                **build_settings().__dict__,
                "default_model": "openai_compat:general",
                "default_fallback_model": "ollama:general",
                "routing_cost_aware_enabled": True,
            }
        )
        router = ModelRouter(settings)
        models = router.candidate_models(TaskType.general, message="hello")
        self.assertEqual(models[0], "ollama:general")


if __name__ == "__main__":
    unittest.main()
