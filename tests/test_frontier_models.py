"""Тесты frontier model ladder (V4-Pro / chain)."""

import unittest

from app.core.config import Settings
from app.core.frontier_models import (
    DEEPSEEK_V3,
    DEEPSEEK_V4_PRO,
    frontier_fallback_chain,
    parse_model_chain,
    resolve_benchmark_reference_model,
    resolve_frontier_model,
)


def _minimal_settings(**overrides: object) -> Settings:
    base = Settings(
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
    return Settings(**{**base.__dict__, **overrides})


class FrontierModelsTests(unittest.TestCase):
    def test_default_frontier_is_v4_pro(self) -> None:
        settings = _minimal_settings()
        self.assertEqual(resolve_frontier_model(settings), DEEPSEEK_V4_PRO)

    def test_parse_model_chain(self) -> None:
        chain = parse_model_chain("a,b,,c")
        self.assertEqual(chain, ["a", "b", "c"])

    def test_frontier_chain_includes_v3_fallback(self) -> None:
        settings = _minimal_settings()
        chain = frontier_fallback_chain(settings)
        self.assertEqual(chain[0], DEEPSEEK_V4_PRO)
        self.assertIn(DEEPSEEK_V3, chain)

    def test_benchmark_reference_explicit_env(self) -> None:
        settings = _minimal_settings(
            eval_benchmark_reference_model="openai_compat:custom/ref",
        )
        self.assertEqual(
            resolve_benchmark_reference_model(settings),
            "openai_compat:custom/ref",
        )


if __name__ == "__main__":
    unittest.main()
