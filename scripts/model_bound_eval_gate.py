#!/usr/bin/env python3
"""Run model-bound eval scenarios and apply tier gate (CI-safe or release)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.eval_ci_gate import (
    MODEL_BOUND_CI_GATE,
    MODEL_BOUND_RELEASE_GATE,
    evaluate_tier_gate,
)
from app.services.eval_quality_judge_service import EvalQualityJudgeService
from app.services.eval_service import EvalService
from app.services.tooling_service import ToolingService
from app.core.model_roles import resolve_cloud_teacher_model
from app.state import _build_llm_caller_service


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


def main() -> int:
    tier_name = os.getenv("TERMIT_MODEL_BOUND_GATE_TIER", "model_bound_ci").strip().lower()
    gate_map = {
        "model_bound_ci": MODEL_BOUND_CI_GATE,
        "model_bound_release": MODEL_BOUND_RELEASE_GATE,
    }
    selected = gate_map.get(tier_name)
    if selected is None:
        print(f"Unknown model-bound gate tier: {tier_name}", file=sys.stderr)
        return 2

    service = _build_eval_service()
    if selected.name == MODEL_BOUND_CI_GATE.name:
        scenario_ids = service.model_bound_tool_scenario_ids()
    else:
        scenario_ids = service.model_bound_scenario_ids()
    if not scenario_ids:
        print("No model-bound scenarios configured.", file=sys.stderr)
        return 2

    report = service.run_scenario_ids(
        scenario_ids,
        persist_report=False,
        category_filter="model_bound",
    )
    ok, message = evaluate_tier_gate(
        tier=selected,
        pass_rate=float(report.get("pass_rate", 0.0)),
        total=int(report.get("total", 0)),
        quality_median=float(report.get("quality_median", 0.0) or 0.0) or None,
        cloud_judge_coverage=float(report.get("cloud_judge_coverage", 0.0) or 0.0),
    )
    print(json.dumps({"gate_passed": ok, "tier": selected.name, "scenario_ids": scenario_ids}, indent=2))
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
