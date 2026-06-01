#!/usr/bin/env python3
"""Export a finetune dataset JSONL from Termit feedback/tasks/agent runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.domain.schemas import FinetuneDatasetExportRequest
from app.services.finetune_service import FinetuneService


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Termit finetune dataset")
    parser.add_argument("--name", default="termit-export", help="Dataset name")
    parser.add_argument("--min-samples", type=int, default=1)
    parser.add_argument("--no-feedback", action="store_true")
    parser.add_argument("--no-tasks", action="store_true")
    parser.add_argument("--no-agent-runs", action="store_true")
    parser.add_argument("--trajectory", action="store_true", help="Also export trajectory SFT JSONL")
    parser.add_argument("--no-dpo", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    service = FinetuneService(
        datasets_dir=settings.finetune_datasets_dir,
        jobs_path=settings.finetune_jobs_path,
        adapters_path=settings.finetune_adapters_path,
        feedback_file_path=settings.feedback_file_path,
        task_sqlite_path=settings.task_sqlite_path,
        agent_run_sqlite_path=settings.agent_run_sqlite_path,
        repo_profiles_path=settings.repo_model_profiles_path,
        memory_sqlite_path=settings.memory_sqlite_path,
    )
    try:
        result = service.export_dataset(
            FinetuneDatasetExportRequest(
                name=args.name,
                include_feedback=not args.no_feedback,
                include_tasks=not args.no_tasks,
                include_agent_runs=not args.no_agent_runs,
                include_dpo_negatives=not args.no_dpo,
                min_samples=args.min_samples,
            )
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    if args.trajectory:
        from app.domain.schemas import FinetuneTrajectoryExportRequest

        try:
            traj = service.export_trajectory_sft(
                FinetuneTrajectoryExportRequest(
                    name=f"{args.name}-trajectory",
                    min_samples=1,
                    limit=300,
                )
            )
        except ValueError as exc:
            print(json.dumps({"trajectory_error": str(exc)}, indent=2))
            return 0
        print(json.dumps({"trajectory_sft": traj}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
