#!/usr/bin/env python3
"""Export trajectory SFT JSONL from agent run events."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.domain.schemas import FinetuneTrajectoryExportRequest
from app.services.finetune_service import FinetuneService


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Termit trajectory SFT dataset")
    parser.add_argument("--name", default="trajectory-export")
    parser.add_argument("--min-samples", type=int, default=1)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    settings = get_settings()
    service = FinetuneService(
        datasets_dir=settings.finetune_datasets_dir,
        agent_run_sqlite_path=settings.agent_run_sqlite_path,
        training_signals_path=settings.finetune_training_signals_path,
    )
    try:
        result = service.export_trajectory_sft(
            FinetuneTrajectoryExportRequest(
                name=args.name,
                min_samples=args.min_samples,
                limit=args.limit,
            )
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
