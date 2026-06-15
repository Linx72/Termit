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
        self._model_cost_overrides = self._parse_cost_overrides(
            getattr(settings, "routing_model_costs", "")
        )

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
            if complexity == "low":
                models = [
                    self.settings.fast_model,
                    self.settings.code_model,
                    self.settings.code_fallback_model,
                ]
            elif complexity == "high":
                models = [
                    self.settings.code_model,
                    self.settings.analysis_model,
                    self.settings.frontier_fallback_model,
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
        if getattr(self.settings, "routing_cost_aware_enabled", False):
            unique = self._apply_cost_aware_ranking(unique, complexity=complexity)
        unique = filter_runtime_candidates(self.settings, unique)
        max_candidates = max(1, getattr(self.settings, "routing_max_candidates", 4))
        return unique[:max_candidates]

    def _apply_cost_aware_ranking(self, models: list[str], *, complexity: str) -> list[str]:
        if len(models) < 2:
            return models
        if complexity == "high":
            return models
        if complexity == "medium":
            head = models[:1]
            tail = sorted(
                models[1:],
                key=lambda model: (self._estimated_model_cost(model), models.index(model)),
            )
            return head + tail
        return sorted(
            models,
            key=lambda model: (self._estimated_model_cost(model), models.index(model)),
        )

    def _estimated_model_cost(self, model: str) -> float:
        if model in self._model_cost_overrides:
            return self._model_cost_overrides[model]
        provider = self.provider_for_model(model)
        if provider == "openai_compat":
            return float(getattr(self.settings, "routing_default_openai_cost_usd", 0.002))
        if provider == "ollama":
            return float(getattr(self.settings, "routing_default_ollama_cost_usd", 0.0))
        return float(getattr(self.settings, "routing_default_openai_cost_usd", 0.002))

    @staticmethod
    def _parse_cost_overrides(raw: str) -> dict[str, float]:
        overrides: dict[str, float] = {}
        if not raw.strip():
            return overrides
        for item in raw.split(","):
            chunk = item.strip()
            if not chunk or "=" not in chunk:
                continue
            model, cost_raw = chunk.rsplit("=", 1)
            model_name = model.strip()
            try:
                cost = float(cost_raw.strip())
            except ValueError:
                continue
            if model_name:
                overrides[model_name] = max(0.0, cost)
        return overrides

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

    def routing_tiers(self) -> dict[str, str]:
        return {
            "fast": self.settings.fast_model,
            "strong_local": self.settings.code_model,
            "frontier_fallback": self.settings.frontier_fallback_model,
        }
