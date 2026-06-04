import unittest

from app.core.config import Settings
from app.core.model_roles import (
    filter_runtime_candidates,
    is_teacher_model,
    resolve_stage1_base_model,
    teacher_ollama_model_names,
)
from app.services.model_router import ModelRouter
from app.domain.schemas import TaskType
from tests.test_model_router import build_settings


def _settings_with_teacher(**overrides: object) -> Settings:
    base = build_settings()
    data = {**base.__dict__, **overrides}
    return Settings(**data)


class ModelRolesTests(unittest.TestCase):
    def test_resolve_stage1_base_model_uses_teacher_when_empty(self) -> None:
        settings = _settings_with_teacher(
            teacher_model="ollama:deepseek-coder",
            stage1_schedule_base_model="",
        )
        self.assertEqual(resolve_stage1_base_model(settings, ""), "ollama:deepseek-coder")

    def test_resolve_stage1_base_model_honors_explicit(self) -> None:
        settings = _settings_with_teacher(teacher_model="ollama:deepseek-coder")
        self.assertEqual(
            resolve_stage1_base_model(settings, "ollama:custom-base"),
            "ollama:custom-base",
        )

    def test_filter_runtime_candidates_removes_teacher_models(self) -> None:
        settings = _settings_with_teacher(
            code_model="ollama:termit-core-ft",
            code_fallback_model="ollama:deepseek-coder",
            teacher_model="ollama:deepseek-coder",
            teacher_fallback_model="openai_compat:deepseek-ai/deepseek-coder-33b-instruct",
        )
        filtered = filter_runtime_candidates(
            settings,
            [
                "ollama:termit-core-ft",
                "ollama:deepseek-coder",
                "openai_compat:deepseek-ai/deepseek-coder-33b-instruct",
            ],
        )
        self.assertEqual(filtered, ["ollama:termit-core-ft"])

    def test_is_teacher_model(self) -> None:
        settings = _settings_with_teacher(teacher_model="ollama:deepseek-coder")
        self.assertTrue(is_teacher_model(settings, "ollama:deepseek-coder"))
        self.assertFalse(is_teacher_model(settings, "ollama:termit-core-ft"))

    def test_teacher_ollama_model_names(self) -> None:
        settings = _settings_with_teacher(
            teacher_model="ollama:deepseek-coder",
            teacher_fallback_model="openai_compat:deepseek-ai/deepseek-coder-33b-instruct",
        )
        self.assertEqual(teacher_ollama_model_names(settings), ["deepseek-coder"])

    def test_model_router_excludes_teacher_from_candidates(self) -> None:
        settings = _settings_with_teacher(
            code_model="ollama:termit-core-ft",
            code_fallback_model="ollama:deepseek-coder",
            teacher_model="ollama:deepseek-coder",
            teacher_fallback_model="",
        )
        router = ModelRouter(settings)
        models = router.candidate_models(TaskType.coding)
        self.assertNotIn("ollama:deepseek-coder", models)
        self.assertEqual(models[0], "ollama:termit-core-ft")


if __name__ == "__main__":
    unittest.main()
