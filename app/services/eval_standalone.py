"""Общие пути extra-сценариев eval и сборка standalone EvalService для скриптов."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.eval_service import EvalService


def extra_eval_scenario_paths(settings: Settings) -> list[str]:
    """IQ + SWE + HumanEval + Terminal-Bench slices для eval/benchmark скриптов."""
    candidates = [
        settings.eval_iq_scenarios_path,
        settings.eval_swe_scenarios_path,
        settings.eval_humaneval_scenarios_path,
        settings.eval_terminal_scenarios_path,
    ]
    return [path for path in candidates if path.strip()]


def default_post_dpo_scenario_ids() -> str:
    """ID сценариев post-DPO: model benchmark + tool fixtures (SWE/Terminal)."""
    import os

    override = os.getenv("TERMIT_EVAL_POST_DPO_IDS", "").strip()
    if override:
        return override
    if os.getenv("TERMIT_EVAL_POST_DPO_FULL", "true").lower() in {"1", "true", "yes"}:
        if os.getenv("TERMIT_LEARNING_LOOP_SKIP_MODEL_BENCHMARK", "").lower() in {
            "1",
            "true",
            "yes",
        }:
            return "HE1,HE2,MBPP1,MBPP2,SWE1,SWE3,SWE5,TB1,TB2,TB3"
        return (
            "MB1,MB2,MB3,MT1,MT2,"
            "HE1,HE2,MBPP1,MBPP2,"
            "SWE1,SWE3,SWE5,TB1,TB2,TB3"
        )
    return os.getenv("TERMIT_EVAL_MODEL_KPI_IDS", "MB1,MB2,MB3")


def build_standalone_eval_service(*, root_path: str | None = None) -> EvalService:
    """EvalService для CLI (post-train, model-bound gate, benchmark) без FastAPI state."""
    from app.core.config import get_settings
    from app.core.model_roles import resolve_cloud_teacher_model
    from app.services.eval_quality_judge_service import EvalQualityJudgeService
    from app.services.eval_service import EvalService
    from app.services.tooling_service import ToolingService
    from app.state import _build_llm_caller_service

    settings = get_settings()
    repo_root = Path(root_path or Path(settings.eval_scenarios_path).parent.parent or ".").resolve()
    llm_caller = _build_llm_caller_service()
    judge_model = settings.eval_quality_judge_model or resolve_cloud_teacher_model(settings)
    quality_judge = EvalQualityJudgeService(
        judge_model=judge_model,
        llm_caller=llm_caller.call,
    )
    return EvalService(
        scenarios_path=settings.eval_scenarios_path,
        tooling_service=ToolingService(root_path=str(repo_root)),
        extra_scenarios_paths=extra_eval_scenario_paths(settings),
        quality_judge=quality_judge,
        llm_caller=llm_caller,
        model_benchmark_scenarios_path=settings.eval_model_benchmark_scenarios_path,
    )
