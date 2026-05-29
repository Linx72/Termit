from typing import Optional

from app.core.config import Settings
from app.domain.schemas import TaskType


class ModelRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def select_model(self, task_type: TaskType, requested_model: Optional[str] = None) -> str:
        if requested_model:
            return requested_model

        if task_type == TaskType.coding:
            return self.settings.code_model
        if task_type in {TaskType.review, TaskType.debug, TaskType.explain}:
            return self.settings.analysis_model
        return self.settings.default_model

    def candidate_models(self, task_type: TaskType, requested_model: Optional[str] = None) -> list[str]:
        if requested_model:
            return [requested_model]

        if task_type == TaskType.coding:
            models = [self.settings.code_model, self.settings.code_fallback_model]
        elif task_type in {TaskType.review, TaskType.debug, TaskType.explain}:
            models = [self.settings.analysis_model, self.settings.analysis_fallback_model]
        else:
            models = [self.settings.default_model, self.settings.default_fallback_model]

        unique: list[str] = []
        for model in models:
            if model and model not in unique:
                unique.append(model)
        return unique

    @staticmethod
    def provider_for_model(model_name: str) -> str:
        if ":" not in model_name:
            return "ollama"
        return model_name.split(":", 1)[0]
