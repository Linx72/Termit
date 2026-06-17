#!/usr/bin/env python3
"""Sync routing benchmark scores from the latest eval baseline comparison report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.eval_service import EvalService
from app.services.routing_benchmark_sync_service import RoutingBenchmarkSyncService
from app.services.routing_policy_service import RoutingPolicyService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update data/routing_benchmarks.json from eval benchmark report",
    )
    parser.add_argument("--blend-alpha", type=float, default=0.3, help="EMA weight on new scores")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--report-file", default="", help="Override eval report JSONL path")
    args = parser.parse_args()

    settings = get_settings()
    report_path = args.report_file or settings.eval_report_file_path
    routing = RoutingPolicyService(
        repo_profiles_path=settings.repo_model_profiles_path,
        benchmarks_path=settings.routing_benchmarks_path,
    )
    eval_service = EvalService(scenarios_path=settings.eval_scenarios_path)
    categories = {item.id: item.category for item in eval_service.list_scenarios()}

    sync = RoutingBenchmarkSyncService(routing, report_file_path=report_path)
    summary = sync.sync_from_latest_report(
        category_by_scenario_id=categories,
        blend_alpha=max(0.0, min(1.0, float(args.blend_alpha))),
        persist=not args.no_persist,
        dry_run=bool(args.dry_run),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
