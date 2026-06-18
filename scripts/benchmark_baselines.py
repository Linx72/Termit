#!/usr/bin/env python3
"""Run Termit vs reference model baseline benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.eval_benchmark_service import EvalBenchmarkService
from app.services.eval_quality_judge_service import EvalQualityJudgeService
from app.services.eval_service import EvalService
from app.state import _build_llm_caller_service


def _load_json(path: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object expected at {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Termit vs reference model")
    parser.add_argument(
        "--scenarios",
        default="model",
        help="Comma-separated scenario ids, or 'model' for model_benchmark suite, or 'model_bound' for full model-bound slice",
    )
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument(
        "--capability-review",
        action="store_true",
        help="Print aggregate review over recent benchmark runs instead of running new benchmark",
    )
    parser.add_argument(
        "--capability-limit",
        type=int,
        default=6,
        help="How many recent benchmark reports to include in capability review",
    )
    parser.add_argument(
        "--capability-regression",
        action="store_true",
        help="Compare capability review against baseline and print regression summary",
    )
    parser.add_argument(
        "--capability-baseline",
        default="",
        help="Capability baseline JSON path (defaults to TERMIT_EVAL_CAPABILITY_BASELINE_PATH)",
    )
    parser.add_argument("--max-pass-gap-drop", type=float, default=-1.0)
    parser.add_argument("--max-quality-gap-drop", type=float, default=-1.0)
    parser.add_argument("--max-win-rate-drop", type=float, default=-1.0)
    parser.add_argument(
        "--refresh-capability-baseline",
        action="store_true",
        help="Recompute and overwrite capability baseline JSON from recent benchmark history",
    )
    parser.add_argument(
        "--capability-baseline-out",
        default="",
        help="Output path for baseline refresh (defaults to TERMIT_EVAL_CAPABILITY_BASELINE_PATH)",
    )
    args = parser.parse_args()

    settings = get_settings()
    benchmark = EvalBenchmarkService(
        report_file_path=settings.eval_report_file_path,
        termit_model=settings.code_model,
        reference_model=settings.eval_benchmark_reference_model,
    )
    if args.capability_review:
        review = benchmark.build_capability_review(limit=max(1, min(args.capability_limit, 52)))
        print(json.dumps(review, indent=2))
        return 0
    if args.capability_regression:
        baseline_path = args.capability_baseline.strip() or settings.eval_capability_baseline_path
        baseline = _load_json(baseline_path)
        regression = benchmark.build_capability_regression(
            baseline=baseline,
            limit=max(1, min(args.capability_limit, 52)),
            max_pass_gap_drop=(
                settings.capability_regression_max_pass_gap_drop
                if args.max_pass_gap_drop < 0
                else max(0.0, args.max_pass_gap_drop)
            ),
            max_quality_gap_drop=(
                settings.capability_regression_max_quality_gap_drop
                if args.max_quality_gap_drop < 0
                else max(0.0, args.max_quality_gap_drop)
            ),
            max_win_rate_drop=(
                settings.capability_regression_max_win_rate_drop
                if args.max_win_rate_drop < 0
                else max(0.0, args.max_win_rate_drop)
            ),
        )
        print(json.dumps(regression, indent=2))
        return 0
    if args.refresh_capability_baseline:
        out_path = args.capability_baseline_out.strip() or settings.eval_capability_baseline_path
        baseline = benchmark.refresh_capability_baseline(
            baseline_file_path=out_path,
            limit=max(1, min(args.capability_limit, 52)),
        )
        print(json.dumps({"baseline_path": out_path, "baseline": baseline}, indent=2))
        return 0

    judge = EvalQualityJudgeService(
        judge_model=settings.eval_quality_judge_model,
        llm_caller=_build_llm_caller_service().call,
    )
    eval_service = EvalService(
        scenarios_path=settings.eval_scenarios_path,
        extra_scenarios_paths=[
            settings.eval_iq_scenarios_path,
            settings.eval_swe_scenarios_path,
            settings.eval_humaneval_scenarios_path,
        ],
        quality_judge=judge,
        llm_caller=_build_llm_caller_service(),
        model_benchmark_scenarios_path=settings.eval_model_benchmark_scenarios_path,
    )
    benchmark = EvalBenchmarkService(
        report_file_path=settings.eval_report_file_path,
        termit_model=settings.code_model,
        reference_model=settings.eval_benchmark_reference_model,
        scenario_runner=lambda scenario_id, model: eval_service.run_scenario(scenario_id, model=model),
        quality_judge=lambda result: float(result.get("quality_score", 0.0) or 0.0),
    )
    if args.scenarios.strip().lower() == "model":
        scenario_ids = eval_service.model_benchmark_scenario_ids()
    elif args.scenarios.strip().lower() == "model_bound":
        scenario_ids = eval_service.model_bound_scenario_ids()
    else:
        scenario_ids = [item.strip() for item in args.scenarios.split(",") if item.strip()]
    report = benchmark.compare_on_scenarios(scenario_ids, persist=not args.no_persist)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
