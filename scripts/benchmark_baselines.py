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


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Termit vs reference model")
    parser.add_argument("--scenarios", default="IQ1,SWE1,IQ2")
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    judge = EvalQualityJudgeService(judge_model=settings.eval_quality_judge_model)
    eval_service = EvalService(
        scenarios_path=settings.eval_scenarios_path,
        extra_scenarios_paths=[
            settings.eval_iq_scenarios_path,
            settings.eval_swe_scenarios_path,
        ],
        quality_judge=judge,
    )
    benchmark = EvalBenchmarkService(
        report_file_path=settings.eval_report_file_path,
        termit_model=settings.code_model,
        reference_model=settings.eval_benchmark_reference_model,
        scenario_runner=lambda scenario_id, _model: eval_service.run_scenario(scenario_id),
        quality_judge=lambda result: float(result.get("quality_score", 0.0) or 0.0),
    )
    scenario_ids = [item.strip() for item in args.scenarios.split(",") if item.strip()]
    report = benchmark.compare_on_scenarios(scenario_ids, persist=not args.no_persist)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
