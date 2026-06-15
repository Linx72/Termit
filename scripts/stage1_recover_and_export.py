#!/usr/bin/env python3
"""Recover stuck Stage1 pipeline runs and export curated training dataset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.finetune_service import FinetuneService


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover stuck Stage1 runs and export dataset")
    parser.add_argument("--stale-seconds", type=int, default=None)
    parser.add_argument("--requeue", action="store_true")
    parser.add_argument("--export-name", default="stage1-signals-export")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--min-samples", type=int, default=10)
    parser.add_argument("--no-export", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    service = FinetuneService(
        datasets_dir=settings.finetune_datasets_dir,
        jobs_path=settings.finetune_jobs_path,
        adapters_path=settings.finetune_adapters_path,
        pipelines_path=settings.finetune_pipelines_path,
        feedback_file_path=settings.feedback_file_path,
        task_sqlite_path=settings.task_sqlite_path,
        agent_run_sqlite_path=settings.agent_run_sqlite_path,
        memory_sqlite_path=settings.memory_sqlite_path,
        training_signals_path=settings.finetune_training_signals_path,
        eval_report_file_path=settings.eval_report_file_path,
        repo_profiles_path=settings.repo_model_profiles_path,
        pipeline_stuck_timeout_seconds=settings.finetune_pipeline_stuck_timeout_seconds,
    )

    recovered = service.recover_stuck_pipeline_runs(
        stale_seconds=args.stale_seconds,
        requeue=args.requeue,
    )
    print(json.dumps({"recovered": recovered, "total": len(recovered)}, indent=2))

    if args.no_export:
        return 0

    try:
        export = service.export_training_signals_dataset(
            name=args.export_name,
            limit=args.limit,
            min_samples=args.min_samples,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"export": export}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
