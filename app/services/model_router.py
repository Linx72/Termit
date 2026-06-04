from typing import TYPE_CHECKING, Optional

from app.domain.schemas import ChatMessage
from app.core.config import Settings
from app.core.model_roles import filter_runtime_candidates
from app.domain.schemas import TaskType

if TYPE_CHECKING:
    from app.services.finetune_adapter_resolver import FinetuneAdapterResolver
    from app.services.routing_policy_service import RoutingPolicyService


class ModelRouter:
    MODEL_PROFILES = {
        "coding-fast": "code_model",
        "coding-strong": "analysis_model",
        "review": "analysis_model",
    }

    def __init__(
        self,
        settings: Settings,
        routing_policy: Optional["RoutingPolicyService"] = None,
    ) -> None:
        self.settings = settings
        self._routing_policy = routing_policy

    def resolve_profile_model(self, profile_name: str) -> Optional[str]:
        key = profile_name.strip().lower()
        attr = self.MODEL_PROFILES.get(key)
        if not attr:
            return None
        value = getattr(self.settings, attr, None)
        return str(value) if value else None

    def select_model(self, task_type: TaskType, requested_model: Optional[str] = None) -> str:
        if requested_model:
            resolved = self.resolve_profile_model(requested_model)
            if resolved:
                return resolved
            return requested_model

        if task_type == TaskType.coding:
            return self.settings.code_model
        if task_type in {TaskType.review, TaskType.debug, TaskType.explain}:
            return self.settings.analysis_model
        if task_type in {TaskType.online_research, TaskType.online_project}:
            return self.settings.analysis_model
        if task_type == TaskType.creative_media:
            return self.settings.analysis_model
        return self.settings.default_model

    def candidate_models(
        self,
        task_type: TaskType,
        requested_model: Optional[str] = None,
        message: str = "",
        history: Optional[list[ChatMessage]] = None,
        repo_profile: Optional[str] = None,
        path_prefix: str = "",
        routing_policy: str = "default",
    ) -> list[str]:
        if requested_model:
            resolved = self.resolve_profile_model(requested_model)
            if resolved:
                return [resolved]
            return [requested_model]

        complexity = self.complexity_tier(task_type=task_type, message=message, history=history or [])

        if task_type == TaskType.coding:
            models = [self.settings.code_model, self.settings.code_fallback_model]
            if complexity == "high":
                models = [
                    self.settings.code_model,
                    self.settings.analysis_model,
                    self.settings.code_fallback_model,
                    self.settings.analysis_fallback_model,
                ]
        elif task_type in {TaskType.review, TaskType.debug, TaskType.explain}:
            models = [self.settings.analysis_model, self.settings.analysis_fallback_model]
        elif task_type in {TaskType.online_research, TaskType.online_project}:
            models = [self.settings.analysis_model, self.settings.default_model]
        elif task_type == TaskType.creative_media:
            models = [self.settings.analysis_model, self.settings.default_model]
        else:
            models = [self.settings.default_model, self.settings.default_fallback_model]
            if complexity == "high":
                models = [
                    self.settings.analysis_model,
                    self.settings.default_model,
                    self.settings.analysis_fallback_model,
                    self.settings.default_fallback_model,
                ]

        unique: list[str] = []
        for model in models:
            if model and model not in unique:
                unique.append(model)

        if self._routing_policy is not None:
            preferred = self._routing_policy.resolve_repo_model(
                profile_id=repo_profile,
                path_prefix=path_prefix,
                task_type=task_type,
            )
            if preferred:
                unique = [preferred] + [item for item in unique if item != preferred]
            if routing_policy == "benchmark":
                unique = self._routing_policy.rank_models_for_task(unique, task_type)
        unique = filter_runtime_candidates(self.settings, unique)
        max_candidates = max(1, getattr(self.settings, "routing_max_candidates", 4))
        return unique[:max_candidates]

    @staticmethod
    def complexity_tier(task_type: TaskType, message: str, history: list[ChatMessage]) -> str:
        if task_type in {TaskType.review, TaskType.debug, TaskType.explain}:
            return "high"

        msg = message.lower()
        history_chars = sum(len(item.content) for item in history)
        total_chars = len(message) + history_chars
        high_markers = [
            "react",
            "tsx",
            "jsx",
            "vite",
            "tailwind",
            "frontend",
            "component",
            "hydration",
            "spa",
            "вёрстк",
            "фронтенд",
            "компонент",
            "architecture",
            "design",
            "migration",
            "security",
            "optimize",
            "performance",
            "refactor",
            "incident",
            "root cause",
            "архитектур",
            "дизайн",
            "миграц",
            "безопас",
            "оптимиз",
            "производительност",
            "рефактор",
            "инцидент",
            "первопричин",
        ]
        if total_chars > 3000 or any(marker in msg for marker in high_markers):
            return "high"
        if total_chars > 1200:
            return "medium"
        return "low"

    @staticmethod
    def provider_for_model(model_name: str) -> str:
        if ":" not in model_name:
            return "ollama"
        return model_name.split(":", 1)[0]
