#!/usr/bin/env python3
"""Export DPO pairs from training signals, validate contract, optional dry-run train."""

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
from app.domain.schemas import FinetuneDpoExportRequest
from app.services.finetune_service import FinetuneService
from app.state import get_finetune_trainer_service


def _build_service() -> FinetuneService:
    settings = get_settings()
    return FinetuneService(
        datasets_dir=settings.finetune_datasets_dir,
        jobs_path=settings.finetune_jobs_path,
        adapters_path=settings.finetune_adapters_path,
        feedback_file_path=settings.feedback_file_path,
        task_sqlite_path=settings.task_sqlite_path,
        agent_run_sqlite_path=settings.agent_run_sqlite_path,
        repo_profiles_path=settings.repo_model_profiles_path,
        memory_sqlite_path=settings.memory_sqlite_path,
        eval_report_file_path=settings.eval_report_file_path,
        training_signals_path=settings.finetune_training_signals_path,
        trainer=get_finetune_trainer_service(),
    )


def _maybe_normalize_signals() -> None:
    if os.getenv("TERMIT_NORMALIZE_SIGNALS_BEFORE_DPO", "true").lower() not in {
        "1",
        "true",
        "yes",
    }:
        return
    settings = get_settings()
    from app.services.training_signal_store import TrainingSignalStore

    store = TrainingSignalStore(
        file_path=settings.finetune_training_signals_path,
        min_output_chars=settings.finetune_min_signal_output_chars,
        enabled=True,
    )
    stats = store.normalize_existing_instructions(preserve_full=True, dry_run=False)
    if int(stats.get("updated", 0)) > 0:
        # stderr: stdout зарезервирован под итоговый JSON export для shell-парсеров
        print(json.dumps({"normalize_signals": stats}, indent=2), file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Termit DPO weekly pipeline")
    parser.add_argument("--name", default="weekly-dpo")
    parser.add_argument("--min-pairs", type=int, default=1)
    parser.add_argument("--min-chosen-chars", type=int, default=12)
    parser.add_argument("--train", action="store_true", help="Run hf_dpo dry-run train after export")
    parser.add_argument("--base-model", default="")
    parser.add_argument(
        "--train-result",
        default="",
        help="Путь для JSON-результата train (последний блок вывода)",
    )
    args = parser.parse_args()

    settings = get_settings()
    _maybe_normalize_signals()
    service = _build_service()
    try:
        export = service.export_dpo_dataset(
            FinetuneDpoExportRequest(
                name=args.name,
                min_pairs=max(1, args.min_pairs),
                min_chosen_chars=max(4, args.min_chosen_chars),
            )
        )
    except ValueError as exc:
        bootstrap_if_empty = os.getenv("TERMIT_DPO_BOOTSTRAP_IF_EMPTY", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        if bootstrap_if_empty:
            from scripts.finetune_bootstrap_signals import main as bootstrap_main

            bootstrap_main()
            try:
                export = service.export_dpo_dataset(
                    FinetuneDpoExportRequest(
                        name=args.name,
                        min_pairs=max(1, args.min_pairs),
                        min_chosen_chars=max(4, args.min_chosen_chars),
                    )
                )
            except ValueError as retry_exc:
                exc = retry_exc
        required = os.getenv("TERMIT_DPO_REQUIRED", "false").lower() in {"1", "true", "yes"}
        print(json.dumps({"skipped": True, "reason": str(exc)}, indent=2))
        return 1 if required else 0

    print(json.dumps(export, indent=2, ensure_ascii=False))

    dataset_path = str(export["dataset_path"])
    gate = service.validate_dpo_dataset(dataset_path=dataset_path, min_text_chars=4)
    if not gate.get("valid", False):
        print("DPO contract validation failed after export.", file=sys.stderr)
        return 1

    if args.train or os.getenv("TERMIT_FINETUNE_AUTO_TRAIN_DPO", "false").lower() in {"1", "true", "yes"}:
        base_model = (
            args.base_model.strip()
            or settings.finetune_output_model
            or settings.code_model
            or "ollama:deepseek-coder"
        )
        train_result = service.train_dpo_dataset(
            dataset_path=dataset_path,
            base_model=base_model,
            trainer_mode="hf_dpo",
        )
        train_text = json.dumps(train_result, indent=2, ensure_ascii=False)
        print(train_text)
        if args.train_result.strip():
            Path(args.train_result.strip()).write_text(train_text + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
