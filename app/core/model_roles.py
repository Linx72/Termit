"""Runtime vs teacher model roles.

Termit inference uses the project's finetuned/runtime weights (``termit-core-ft``).
Teacher models (e.g. DeepSeek) are for stage-1 distillation and finetune only — never
auto-selected in chat/agent routing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings


def bare_ollama_name(model_id: str) -> str:
    candidate = model_id.strip()
    if candidate.startswith("ollama:"):
        return candidate.split(":", 1)[1].strip()
    return candidate


def teacher_model_ids(settings: Settings) -> frozenset[str]:
    """Models reserved for distillation/train only — excluded from agent/chat routing."""
    ids: list[str] = []
    for raw in (
        settings.teacher_model,
        settings.teacher_fallback_model,
    ):
        value = raw.strip()
        if value:
            ids.append(value)
    return frozenset(ids)


def is_teacher_model(settings: Settings, model_name: str) -> bool:
    return model_name.strip() in teacher_model_ids(settings)


def filter_runtime_candidates(settings: Settings, models: list[str]) -> list[str]:
    teachers = teacher_model_ids(settings)
    return [model for model in models if model not in teachers]


def resolve_cloud_teacher_model(settings: Settings) -> str:
    from app.core.frontier_models import resolve_frontier_model

    cloud = settings.cloud_teacher_model.strip()
    if cloud:
        return cloud
    fallback = settings.teacher_fallback_model.strip()
    if fallback.startswith("openai_compat:"):
        return fallback
    frontier = resolve_frontier_model(settings)
    if frontier.startswith("openai_compat:"):
        return frontier
    return settings.teacher_model.strip() or "ollama:deepseek-coder"


def resolve_stage1_base_model(settings: Settings, base_model: str) -> str:
    explicit = (base_model or "").strip()
    if explicit:
        return explicit
    scheduled = settings.stage1_schedule_base_model.strip()
    if scheduled:
        return scheduled
    teacher = settings.teacher_model.strip()
    if teacher:
        return teacher
    return "ollama:deepseek-coder"


def teacher_ollama_model_names(settings: Settings) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for model_id in teacher_model_ids(settings):
        if not model_id.startswith("ollama:"):
            continue
        bare = bare_ollama_name(model_id)
        if bare and bare not in seen:
            seen.add(bare)
            names.append(bare)
    return names
