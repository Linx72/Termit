#!/usr/bin/env python3
"""First Stage1 train: dataset export -> modelfile/QLoRA train -> regression gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.domain.schemas import FinetuneStage1RunRequest
from app.services.eval_service import EvalService
from app.services.finetune_service import FinetuneService
from app.services.finetune_trainer_service import FinetuneTrainerService


def _build_services():
    settings = get_settings()
    trainer = FinetuneTrainerService(
        modelfiles_dir=settings.finetune_modelfiles_dir,
        adapters_dir=settings.finetune_adapters_dir,
        ollama_bin=settings.finetune_ollama_bin,
        ollama_base_url=settings.ollama_base_url,
        default_output_model=settings.finetune_output_model,
        trainer_mode=settings.finetune_trainer,
        train_timeout_seconds=settings.finetune_train_timeout_seconds,
        hf_dry_run=settings.finetune_hf_dry_run,
        hf_epochs=settings.finetune_hf_epochs,
        hf_lora_rank=settings.finetune_hf_lora_rank,
        hf_max_samples=settings.finetune_hf_max_samples,
        hf_auto_gguf=settings.finetune_hf_auto_gguf,
        hf_auto_ollama=settings.finetune_hf_auto_ollama,
        llama_cpp_path=settings.finetune_llama_cpp_path,
    )

    def post_eval_runner(request: FinetuneStage1RunRequest) -> dict[str, object]:
        return EvalService(
            scenarios_path=settings.eval_scenarios_path,
            extra_scenarios_paths=[
                settings.eval_iq_scenarios_path,
                settings.eval_swe_scenarios_path,
            ],
        ).run_suite(limit=request.eval_limit or 24, persist_report=True)

    finetune = FinetuneService(
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
        trainer=trainer,
        auto_train_after_pipeline=True,
        auto_register_after_train=settings.finetune_auto_register_after_train,
        auto_post_eval=settings.finetune_auto_post_eval,
        post_eval_runner=post_eval_runner,
        regression_gate_enabled=settings.finetune_regression_gate_enabled,
        regression_require_post_eval=settings.finetune_regression_require_post_eval,
        max_train_regression=settings.finetune_max_train_regression,
        shadow_traffic_percent=settings.finetune_shadow_traffic_percent,
    )
    return settings, finetune


def main() -> int:
    parser = argparse.ArgumentParser(description="Run first Stage1 train cycle")
    parser.add_argument("--trainer", choices=["ollama", "modelfile", "hf"], default=None)
    parser.add_argument("--base-model", default="ollama:deepseek-coder")
    parser.add_argument("--output-model", default=None)
    parser.add_argument("--min-samples", type=int, default=10)
    args = parser.parse_args()

    settings, service = _build_services()
    service.recover_stuck_pipeline_runs(requeue=False)

    export = service.export_training_signals_dataset(
        name="stage1-first-train",
        limit=500,
        min_samples=args.min_samples,
    )
    baseline = EvalService(
        scenarios_path=settings.eval_scenarios_path,
        extra_scenarios_paths=[
            settings.eval_iq_scenarios_path,
            settings.eval_swe_scenarios_path,
        ],
    ).run_suite(limit=24, persist_report=True)

    payload = FinetuneStage1RunRequest(
        name="stage1-first-train",
        base_model=args.base_model,
        min_samples=args.min_samples,
        run_eval_baseline=True,
        run_post_eval=True,
        eval_limit=24,
        auto_register_adapter=True,
        adapter_name="termit-core-ft-v0",
        adapter_model=f"ollama:{args.output_model or settings.finetune_output_model}",
        repo_profile_id=settings.finetune_repo_profile_id,
    )
    pipeline = service.run_stage1_pipeline(payload, baseline_report=baseline)
    pipeline = service._maybe_auto_train_pipeline("manual-first-train", pipeline, payload)
    pipeline = service._maybe_post_eval_pipeline("manual-first-train", pipeline, payload)
    pipeline = service._finalize_training_deploy("manual-first-train", pipeline, payload)

    trainer_mode = args.trainer or settings.finetune_trainer
    if trainer_mode in {"ollama", "modelfile", "hf"} and service._trainer is not None:
        train_result = service._trainer.train_dataset(
            dataset_path=str(export["dataset_path"]),
            base_model=args.base_model,
            output_model=args.output_model or settings.finetune_output_model,
            trainer_mode=trainer_mode,
            repo_profile_id=settings.finetune_repo_profile_id,
        )
        pipeline["manual_train"] = train_result.to_dict()

    print(json.dumps({"export": export, "baseline": baseline, "pipeline": pipeline}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
