#!/usr/bin/env python3
"""Запуск model_llm benchmark-среза с указанной моделью (KPI до/после finetune)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.core.model_roles import resolve_cloud_teacher_model
from app.services.eval_quality_judge_service import EvalQualityJudgeService
from app.services.eval_service import EvalService
from app.services.tooling_service import ToolingService
from app.state import _build_llm_caller_service


def _normalize_model(raw: str) -> str:
    model = raw.strip()
    if not model:
        return model
    if model.startswith("ollama:"):
        return model
    return f"ollama:{model}"


def _build_eval_service() -> EvalService:
    settings = get_settings()
    llm_caller = _build_llm_caller_service()
    judge_model = settings.eval_quality_judge_model or resolve_cloud_teacher_model(settings)
    quality_judge = EvalQualityJudgeService(
        judge_model=judge_model,
        llm_caller=llm_caller.call,
    )
    tooling = ToolingService(root_path=str(ROOT))
    return EvalService(
        scenarios_path=settings.eval_scenarios_path,
        tooling_service=tooling,
        extra_scenarios_paths=[
            settings.eval_humaneval_scenarios_path,
        ],
        quality_judge=quality_judge,
        llm_caller=llm_caller,
        model_benchmark_scenarios_path=settings.eval_model_benchmark_scenarios_path,
    )


def _parse_scenario_ids(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Model-bound LLM eval для finetune KPI")
    parser.add_argument("--model", required=True, help="ID модели, напр. ollama:termit-core-ft")
    parser.add_argument(
        "--scenario-ids",
        default=os.getenv("TERMIT_EVAL_MODEL_KPI_IDS", "MB1,MB2,MB3"),
        help="ID сценариев через запятую (по умолчанию MB1,MB2,MB3)",
    )
    parser.add_argument("--output", required=True, help="Путь JSON-отчёта")
    parser.add_argument("--persist-report", action="store_true", help="Сохранить отчёт в eval store")
    args = parser.parse_args()

    scenario_ids = _parse_scenario_ids(args.scenario_ids)
    if not scenario_ids:
        print("Не заданы scenario ids.", file=sys.stderr)
        return 2

    model = _normalize_model(args.model)
    service = _build_eval_service()
    report = service.run_scenario_ids(
        scenario_ids,
        persist_report=args.persist_report,
        category_filter="model_benchmark_kpi",
        model=model,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"pass_rate": report["pass_rate"], "eval_model": model, "output": str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
