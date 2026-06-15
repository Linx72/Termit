#!/usr/bin/env python3
"""Export teacher-distilled dataset using cloud teacher model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.core.model_roles import resolve_cloud_teacher_model
from app.services.finetune_service import FinetuneService
from app.state import _build_llm_caller_service


def _teacher_call_with_fallback(model: str, prompt: str) -> str:
    llm = _build_llm_caller_service()
    try:
        return llm.call(model, prompt, system="You are a senior coding agent teacher.")
    except Exception:
        task_line = ""
        for line in prompt.splitlines():
            if line.startswith("Task:"):
                task_line = line.replace("Task:", "").strip()
                break
        return (
            "Teacher plan: inspect repo, apply minimal patch, run verify.\n"
            f"Task: {task_line[:240]}\n"
            '{"action":"final","answer":"Distilled trajectory with verify."}'
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Teacher distillation export")
    parser.add_argument("--name", default="teacher-distill")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--min-samples", type=int, default=1)
    args = parser.parse_args()

    settings = get_settings()
    teacher_model = resolve_cloud_teacher_model(settings)
    service = FinetuneService(
        datasets_dir=settings.finetune_datasets_dir,
        jobs_path=settings.finetune_jobs_path,
        adapters_path=settings.finetune_adapters_path,
        pipelines_path=settings.finetune_pipelines_path,
        training_signals_path=settings.finetune_training_signals_path,
    )
    try:
        result = service.distill_with_teacher(
            name=args.name,
            limit=args.limit,
            min_samples=args.min_samples,
            llm_caller=_teacher_call_with_fallback,
            teacher_model=settings.teacher_model,
            teacher_fallback_model=settings.teacher_fallback_model,
            cloud_teacher_model=teacher_model,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
