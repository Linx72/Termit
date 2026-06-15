from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Callable, Optional
from uuid import uuid4

from app.domain.schemas import (
    FinetuneAdapterRegisterRequest,
    FinetuneDatasetExportRequest,
    FinetuneDpoExportRequest,
    FinetuneStage1RunRequest,
    FinetuneTrajectoryExportRequest,
)
from app.services.finetune_dpo_export import build_dpo_pairs, write_dpo_jsonl
from app.services.finetune_trainer_service import FinetuneTrainerService
from app.services.finetune_dataset_curator import (
    CuratorConfig,
    curate_samples,
    export_row,
)
from app.services.finetune_regression_gate import evaluate_training_regression
from app.services.finetune_trajectory_export import (
    load_trajectory_sft_rows,
    write_sft_jsonl,
)
from app.services.tool_loop_tuning_service import build_tool_loop_tuning_report
from app.services.training_signal_store import TrainingSignalStore


@dataclass(frozen=True)
class FinetuneJobRecord:
    job_id: str
    name: str
    status: str
    dataset_path: str
    sample_count: int
    base_model: str
    created_at: str
    updated_at: str
    notes: str = ""
    adapter_model: Optional[str] = None


@dataclass(frozen=True)
class FinetunePipelineRunRecord:
    run_id: str
    status: str
    created_at: str
    updated_at: str
    cancelled: bool
    request: dict[str, object]
    result: Optional[dict[str, object]] = None
    error: Optional[str] = None
    stages: list[dict[str, str]] | None = None


class FinetuneService:
    def __init__(
        self,
        *,
        datasets_dir: str = "./data/finetune/datasets",
        jobs_path: str = "./data/finetune/jobs.json",
        adapters_path: str = "./data/finetune/adapters.json",
        feedback_file_path: str = "./data/feedback.jsonl",
        task_sqlite_path: str = "./termit_tasks.db",
        agent_run_sqlite_path: str = "./termit_agent_runs.db",
        memory_sqlite_path: str = "./termit_memory.db",
        training_signals_path: str = "./data/finetune/training_signals.jsonl",
        eval_report_file_path: str = "./data/eval_reports.jsonl",
        repo_profiles_path: str = "./data/repo_model_profiles.json",
        pipelines_path: str = "./data/finetune/pipelines.json",
        pipeline_max_concurrency: int = 1,
        pipeline_stuck_timeout_seconds: int = 3600,
        trainer: Optional[FinetuneTrainerService] = None,
        auto_train_after_pipeline: bool = False,
        auto_register_after_train: bool = False,
        auto_post_eval: bool = True,
        post_eval_runner: Optional[Callable[[FinetuneStage1RunRequest], dict[str, object]]] = None,
        training_signal_store: Optional[TrainingSignalStore] = None,
        regression_gate_enabled: bool = True,
        regression_require_post_eval: bool = True,
        max_train_regression: float = 0.02,
        shadow_traffic_percent: float = 10.0,
    ) -> None:
        self.datasets_dir = Path(datasets_dir)
        self.jobs_path = Path(jobs_path)
        self.adapters_path = Path(adapters_path)
        self.feedback_file_path = Path(feedback_file_path)
        self.task_sqlite_path = Path(task_sqlite_path)
        self.agent_run_sqlite_path = Path(agent_run_sqlite_path)
        self.memory_sqlite_path = Path(memory_sqlite_path)
        self.eval_report_file_path = Path(eval_report_file_path)
        self.repo_profiles_path = Path(repo_profiles_path)
        self.pipelines_path = Path(pipelines_path)
        self._pipeline_max_concurrency = max(1, pipeline_max_concurrency)
        self._pipeline_stuck_timeout_seconds = max(60, pipeline_stuck_timeout_seconds)
        self._trainer = trainer
        self._auto_train_after_pipeline = auto_train_after_pipeline
        self._auto_register_after_train = auto_register_after_train
        self._auto_post_eval = auto_post_eval
        self._post_eval_runner = post_eval_runner
        self._training_signal_store = training_signal_store or TrainingSignalStore(
            training_signals_path
        )
        self._regression_gate_enabled = regression_gate_enabled
        self._regression_require_post_eval = regression_require_post_eval
        self._max_train_regression = max(0.0, max_train_regression)
        self._shadow_traffic_percent = max(0.0, min(shadow_traffic_percent, 100.0))
        self._lock = Lock()
        self._drain_lock = Lock()
        self.datasets_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_path.parent.mkdir(parents=True, exist_ok=True)
        self.adapters_path.parent.mkdir(parents=True, exist_ok=True)
        self.pipelines_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.jobs_path.exists():
            self._write_jobs([])
        if not self.adapters_path.exists():
            self._write_adapters([])
        if not self.pipelines_path.exists():
            self._write_pipeline_runs([])

    def export_dataset(self, payload: FinetuneDatasetExportRequest) -> dict[str, object]:
        raw_samples: list[dict[str, str]] = []
        if payload.include_feedback:
            raw_samples.extend(self._load_feedback_samples(payload.min_rating))
        if payload.include_tasks:
            raw_samples.extend(
                self._load_task_samples(payload.limit, include_trajectory=payload.include_trajectory)
            )
        if payload.include_agent_runs:
            raw_samples.extend(
                self._load_agent_run_samples(
                    payload.limit,
                    include_trajectory=payload.include_trajectory,
                )
            )
        if payload.include_chat_sessions:
            raw_samples.extend(self._load_chat_session_samples(payload.limit))
        if payload.include_training_signals:
            raw_samples.extend(self._training_signal_store.load_samples(payload.limit))
        if payload.include_dpo_negatives:
            raw_samples.extend(self._training_signal_store.load_dpo_samples(payload.limit))

        sources_manifest = self._count_sources(raw_samples)

        if payload.prefer_eval_passed:
            raw_samples = self._apply_eval_passed_boost(raw_samples)

        max_per_category = payload.curate_max_per_category
        if payload.curate_stratified_balance and max_per_category is None:
            max_per_category = max(5, payload.limit // 6)

        curated, curation_stats = curate_samples(
            raw_samples,
            CuratorConfig(
                deduplicate=payload.curate_deduplicate,
                dedup_output_prefix_len=payload.curate_dedup_output_prefix_len,
                min_output_chars=payload.curate_min_output_chars,
                max_output_chars=payload.curate_max_output_chars,
                skip_error_patterns=payload.curate_skip_error_patterns,
                stratified_balance=payload.curate_stratified_balance,
                max_per_category=max_per_category,
            ),
        )

        if len(curated) < payload.min_samples:
            raise ValueError(
                f"Dataset has {len(curated)} curated samples "
                f"(raw={curation_stats.raw_count}); minimum required is {payload.min_samples}."
            )

        slug = payload.name.strip().replace(" ", "_").lower()[:40] or "dataset"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dataset_path = self.datasets_dir / f"{slug}_{timestamp}.jsonl"
        with dataset_path.open("w", encoding="utf-8") as handle:
            for row in curated:
                handle.write(json.dumps(export_row(row), ensure_ascii=False) + "\n")

        return {
            "name": payload.name,
            "dataset_path": str(dataset_path),
            "sample_count": len(curated),
            "format": "jsonl",
            "fields": [
                "instruction",
                "input",
                "output",
                "source",
                "category",
                "session_id",
                "task_id",
                "run_id",
                "rating",
                "quality_score",
            ],
            "curation": curation_stats.as_dict(),
            "sources": sources_manifest,
        }

    def export_trajectory_sft(self, payload: FinetuneTrajectoryExportRequest) -> dict[str, object]:
        rows, stats = load_trajectory_sft_rows(
            self.agent_run_sqlite_path,
            limit=payload.limit,
            success_only=payload.success_only,
            min_messages=payload.min_messages,
            system_prompt=payload.system_prompt,
        )
        if stats.exported < payload.min_samples:
            raise ValueError(
                f"Trajectory SFT export has {stats.exported} samples; "
                f"minimum required is {payload.min_samples}."
            )
        slug = payload.name.strip().replace(" ", "_").lower()[:40] or "trajectory"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dataset_path = self.datasets_dir / f"{slug}_sft_{timestamp}.jsonl"
        write_sft_jsonl(dataset_path, rows)
        return {
            "name": payload.name,
            "dataset_path": str(dataset_path),
            "sample_count": stats.exported,
            "format": "sft_chat_jsonl",
            "stats": stats.as_dict(),
        }

    def export_dpo_dataset(self, payload: FinetuneDpoExportRequest) -> dict[str, object]:
        negatives = self._training_signal_store.load_dpo_samples(payload.limit)
        positives = [
            row
            for row in self._training_signal_store.load_samples(payload.limit)
            if str(row.get("origin", "")) not in {"tool_step_negative", "patch_revert"}
        ]
        pairs = build_dpo_pairs(
            negatives,
            positives,
            min_chosen_chars=payload.min_chosen_chars,
        )
        if len(pairs) < payload.min_pairs:
            raise ValueError(
                f"DPO export has {len(pairs)} pairs "
                f"(negatives={len(negatives)}, positive_pool={len(positives)}); "
                f"minimum required is {payload.min_pairs}."
            )
        slug = payload.name.strip().replace(" ", "_").lower()[:40] or "dpo"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dataset_path = self.datasets_dir / f"{slug}_dpo_{timestamp}.jsonl"
        write_dpo_jsonl(dataset_path, pairs)
        return {
            "name": payload.name,
            "dataset_path": str(dataset_path),
            "pair_count": len(pairs),
            "format": "dpo_jsonl",
            "negative_count": len(negatives),
            "positive_pool": len(positives),
        }

    def create_job(
        self,
        *,
        name: str,
        dataset_path: str,
        sample_count: int,
        base_model: str,
        notes: str = "",
    ) -> FinetuneJobRecord:
        now = datetime.now(timezone.utc).isoformat()
        job = FinetuneJobRecord(
            job_id=f"ft_{uuid4().hex[:12]}",
            name=name,
            status="queued",
            dataset_path=dataset_path,
            sample_count=sample_count,
            base_model=base_model,
            created_at=now,
            updated_at=now,
            notes=notes,
        )
        with self._lock:
            jobs = self._read_jobs()
            jobs.append(job)
            self._write_jobs(jobs)
        return job

    def run_job(self, job_id: str) -> FinetuneJobRecord:
        with self._lock:
            jobs = self._read_jobs()
            job = next((item for item in jobs if item.job_id == job_id), None)
            if job is None:
                raise ValueError(f"Unknown finetune job: {job_id}")
            if not Path(job.dataset_path).exists():
                raise ValueError(f"Dataset file missing: {job.dataset_path}")

            updated = FinetuneJobRecord(
                job_id=job.job_id,
                name=job.name,
                status="completed",
                dataset_path=job.dataset_path,
                sample_count=job.sample_count,
                base_model=job.base_model,
                created_at=job.created_at,
                updated_at=datetime.now(timezone.utc).isoformat(),
                notes=(
                    job.notes
                    + " MVP job validated dataset and marked ready for external trainer "
                    "(Ollama Modelfile / HF / Unsloth)."
                ).strip(),
                adapter_model=job.adapter_model,
            )
            jobs = [updated if item.job_id == job_id else item for item in jobs]
            self._write_jobs(jobs)
        return updated

    def list_jobs(self) -> list[FinetuneJobRecord]:
        with self._lock:
            return list(self._read_jobs())

    def get_job(self, job_id: str) -> Optional[FinetuneJobRecord]:
        return next((item for item in self.list_jobs() if item.job_id == job_id), None)

    def register_adapter(self, payload: FinetuneAdapterRegisterRequest) -> dict[str, object]:
        now = datetime.now(timezone.utc).isoformat()
        adapter = {
            "adapter_id": f"fta_{uuid4().hex[:10]}",
            "name": payload.name,
            "model": payload.model,
            "base_model": payload.base_model,
            "repo_profile_id": payload.repo_profile_id,
            "description": payload.description,
            "registered_at": now,
        }
        with self._lock:
            adapters = self._read_adapters()
            for index, existing in enumerate(adapters):
                if (
                    str(existing.get("model", "")).strip() == payload.model.strip()
                    and str(existing.get("base_model", "")).strip() == payload.base_model.strip()
                    and str(existing.get("repo_profile_id", "")).strip()
                    == (payload.repo_profile_id or "").strip()
                ):
                    adapter["adapter_id"] = str(existing.get("adapter_id") or adapter["adapter_id"])
                    adapter["registered_at"] = str(existing.get("registered_at") or now)
                    adapters[index] = adapter
                    self._write_adapters(adapters)
                    if payload.repo_profile_id:
                        self._upsert_repo_profile_model(payload.repo_profile_id, payload.model)
                        self._write_repo_adapter_snapshot(payload.repo_profile_id, adapter)
                    return adapter
            adapters.append(adapter)
            self._write_adapters(adapters)
            if payload.repo_profile_id:
                self._upsert_repo_profile_model(payload.repo_profile_id, payload.model)
                self._write_repo_adapter_snapshot(payload.repo_profile_id, adapter)
        return adapter

    def _write_repo_adapter_snapshot(self, repo_profile_id: str, adapter: dict[str, object]) -> None:
        repo_dir = self.datasets_dir.parent / "adapters" / repo_profile_id
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / "latest.json").write_text(json.dumps(adapter, indent=2), encoding="utf-8")

    def list_adapters(self) -> list[dict[str, object]]:
        with self._lock:
            return list(self._read_adapters())

    def train_job(
        self,
        job_id: str,
        *,
        output_model: Optional[str] = None,
        trainer_mode: Optional[str] = None,
        auto_register_adapter: bool = False,
        adapter_name: Optional[str] = None,
        adapter_model: Optional[str] = None,
        base_model: Optional[str] = None,
        repo_profile_id: Optional[str] = None,
        adapter_description: str = "",
        dataset_path: Optional[str] = None,
    ) -> dict[str, object]:
        if self._trainer is None:
            raise ValueError("Finetune trainer is not configured.")
        job = self.get_job(job_id)
        if job is None:
            raise ValueError(f"Unknown finetune job: {job_id}")
        resolved_dataset = dataset_path or job.dataset_path
        train_result = self._trainer.train_dataset(
            dataset_path=resolved_dataset,
            base_model=base_model or job.base_model,
            output_model=output_model,
            trainer_mode=trainer_mode,
            job_id=job.job_id,
            repo_profile_id=repo_profile_id,
        )
        adapter: Optional[dict[str, object]] = None
        if train_result.status == "completed" and train_result.output_model:
            self._update_job_adapter_model(job_id, train_result.output_model)
            if auto_register_adapter or self._auto_register_after_train:
                resolved_name = adapter_name or f"{job.name}-ft"
                resolved_model = adapter_model or f"ollama:{train_result.output_model}"
                adapter = self.register_adapter(
                    FinetuneAdapterRegisterRequest(
                        name=resolved_name,
                        model=resolved_model,
                        base_model=base_model or job.base_model,
                        repo_profile_id=repo_profile_id,
                        description=adapter_description or f"Auto-trained from job {job_id}",
                    )
                )
        payload = train_result.to_dict()
        payload["job_id"] = job_id
        payload["adapter"] = adapter
        return payload

    def train_from_stage1_run(
        self,
        run_id: str,
        *,
        output_model: Optional[str] = None,
        trainer_mode: Optional[str] = None,
        auto_register_adapter: bool = False,
        adapter_name: Optional[str] = None,
        adapter_model: Optional[str] = None,
        repo_profile_id: Optional[str] = None,
        adapter_description: str = "",
    ) -> dict[str, object]:
        run = self.get_stage1_pipeline_run(run_id)
        if run is None:
            raise ValueError(f"Unknown stage1 pipeline run: {run_id}")
        if run["status"] != "completed" or not run.get("result"):
            raise ValueError(f"Stage1 run {run_id} is not completed.")
        return self.train_from_pipeline_result(
            run_id,
            result=run["result"],
            request=FinetuneStage1RunRequest(**run["request"]),
            output_model=output_model,
            trainer_mode=trainer_mode,
            auto_register_adapter=auto_register_adapter,
            adapter_name=adapter_name,
            adapter_model=adapter_model,
            repo_profile_id=repo_profile_id,
            adapter_description=adapter_description,
        )

    def train_from_pipeline_result(
        self,
        run_id: str,
        *,
        result: dict[str, object],
        request: FinetuneStage1RunRequest,
        output_model: Optional[str] = None,
        trainer_mode: Optional[str] = None,
        auto_register_adapter: bool = False,
        adapter_name: Optional[str] = None,
        adapter_model: Optional[str] = None,
        repo_profile_id: Optional[str] = None,
        adapter_description: str = "",
    ) -> dict[str, object]:
        job_info = result.get("job") or {}
        job_id = str(job_info.get("job_id", ""))
        if not job_id:
            raise ValueError("Stage1 run result has no job_id.")
        trajectory = result.get("trajectory_sft")
        dataset_override: Optional[str] = None
        active_mode = (trainer_mode or (self._trainer.trainer_mode if self._trainer else "")).lower()
        if active_mode == "hf" and isinstance(trajectory, dict):
            path = trajectory.get("dataset_path")
            if path:
                dataset_override = str(path)
        train_payload = self.train_job(
            job_id,
            output_model=output_model,
            trainer_mode=trainer_mode,
            auto_register_adapter=(
                (auto_register_adapter or request.auto_register_adapter)
                and not self._should_defer_adapter_registration(request)
            ),
            adapter_name=adapter_name or request.adapter_name,
            adapter_model=adapter_model or request.adapter_model,
            base_model=str(job_info.get("base_model") or request.base_model),
            repo_profile_id=repo_profile_id or request.repo_profile_id,
            adapter_description=adapter_description or request.adapter_description,
            dataset_path=dataset_override,
        )
        train_payload["run_id"] = run_id
        if self._should_defer_adapter_registration(request):
            train_payload["deferred_registration"] = True
        self._append_pipeline_stage(
            run_id,
            {
                "stage": "model_train",
                "status": str(train_payload.get("status", "failed")),
                "detail": str(train_payload.get("detail", "")),
            },
        )
        return train_payload

    def _update_job_adapter_model(self, job_id: str, adapter_model: str) -> None:
        with self._lock:
            jobs = self._read_jobs()
            updated_jobs: list[FinetuneJobRecord] = []
            for item in jobs:
                if item.job_id != job_id:
                    updated_jobs.append(item)
                    continue
                updated_jobs.append(
                    FinetuneJobRecord(
                        job_id=item.job_id,
                        name=item.name,
                        status=item.status,
                        dataset_path=item.dataset_path,
                        sample_count=item.sample_count,
                        base_model=item.base_model,
                        created_at=item.created_at,
                        updated_at=datetime.now(timezone.utc).isoformat(),
                        notes=item.notes,
                        adapter_model=adapter_model,
                    )
                )
            self._write_jobs(updated_jobs)

    def _maybe_auto_train_pipeline(
        self,
        run_id: str,
        result: dict[str, object],
        request: FinetuneStage1RunRequest,
    ) -> dict[str, object]:
        if not self._auto_train_after_pipeline or self._trainer is None:
            return result
        if not self._trainer.auto_train_enabled:
            return result
        try:
            train_payload = self.train_from_pipeline_result(
                run_id,
                result=result,
                request=request,
            )
            merged = dict(result)
            merged["training"] = train_payload
            merged = self._maybe_post_eval_pipeline(run_id, merged, request)
            merged = self._finalize_training_deploy(run_id, merged, request)
            return merged
        except Exception as exc:  # noqa: BLE001
            self._append_pipeline_stage(
                run_id,
                {
                    "stage": "model_train",
                    "status": "failed",
                    "detail": str(exc)[:500],
                },
            )
            merged = dict(result)
            merged["training"] = {"status": "failed", "detail": str(exc)}
            return merged

    def _maybe_post_eval_pipeline(
        self,
        run_id: str,
        result: dict[str, object],
        request: FinetuneStage1RunRequest,
    ) -> dict[str, object]:
        training = result.get("training")
        if not isinstance(training, dict):
            return result
        if str(training.get("status", "")) != "completed":
            return result
        if not request.run_post_eval or not self._auto_post_eval:
            return result
        if self._post_eval_runner is None:
            return result
        try:
            report = self._post_eval_runner(request)
            merged = dict(result)
            merged["post_eval"] = report
            pass_rate = float(report.get("pass_rate", 0.0))
            total = int(report.get("total", 0))
            self._append_pipeline_stage(
                run_id,
                {
                    "stage": "post_train_eval",
                    "status": "completed",
                    "detail": f"Post-train eval pass rate {pass_rate:.2%} on {total} scenarios",
                },
            )
            return merged
        except Exception as exc:  # noqa: BLE001
            self._append_pipeline_stage(
                run_id,
                {
                    "stage": "post_train_eval",
                    "status": "failed",
                    "detail": str(exc)[:500],
                },
            )
            merged = dict(result)
            merged["post_eval"] = {"status": "failed", "detail": str(exc)}
            return merged

    def _should_defer_adapter_registration(self, request: FinetuneStage1RunRequest) -> bool:
        if not self._regression_gate_enabled:
            return False
        wants_register = request.auto_register_adapter or self._auto_register_after_train
        return wants_register and (request.run_post_eval and self._auto_post_eval)

    def _finalize_training_deploy(
        self,
        run_id: str,
        result: dict[str, object],
        request: FinetuneStage1RunRequest,
    ) -> dict[str, object]:
        training = result.get("training")
        if not isinstance(training, dict):
            return result
        if str(training.get("status", "")) != "completed":
            return result
        if not training.get("deferred_registration"):
            return result

        post_eval = result.get("post_eval")
        post_rate: Optional[float] = None
        if isinstance(post_eval, dict) and "pass_rate" in post_eval:
            post_rate = float(post_eval["pass_rate"])

        baseline_rate = result.get("baseline_pass_rate")
        baseline = float(baseline_rate) if baseline_rate is not None else None

        decision = evaluate_training_regression(
            baseline_pass_rate=baseline,
            post_pass_rate=post_rate,
            max_regression=self._max_train_regression,
            shadow_on_regression=True,
            require_post_eval=self._regression_require_post_eval,
        )
        training["regression"] = decision.as_dict()
        if decision.delta is not None:
            training["eval_improvement_delta"] = decision.delta
            if decision.delta < 0.05:
                training["eval_improvement_warning"] = (
                    f"Eval improvement {decision.delta:+.2%} below +5% target after finetune."
                )

        output_model = training.get("output_model")
        repo_profile_id = request.repo_profile_id
        resolved_name = request.adapter_name or f"{request.name}-ft"
        resolved_model = request.adapter_model or (
            f"ollama:{output_model}" if output_model else ""
        )

        if decision.promote and resolved_model:
            adapter = self.register_adapter(
                FinetuneAdapterRegisterRequest(
                    name=resolved_name,
                    model=resolved_model,
                    base_model=request.base_model,
                    repo_profile_id=repo_profile_id,
                    description=request.adapter_description or "Promoted after regression gate.",
                )
            )
            training["adapter"] = adapter
            self._append_pipeline_stage(
                run_id,
                {
                    "stage": "adapter_register",
                    "status": "completed",
                    "detail": decision.reason,
                },
            )
        elif decision.use_shadow and repo_profile_id and resolved_model:
            self._upsert_repo_profile_shadow(
                repo_profile_id,
                resolved_model,
                self._shadow_traffic_percent,
            )
            training["adapter"] = {
                "status": "shadow",
                "model": resolved_model,
                "repo_profile_id": repo_profile_id,
                "shadow_traffic_percent": self._shadow_traffic_percent,
            }
            self._append_pipeline_stage(
                run_id,
                {
                    "stage": "adapter_register",
                    "status": "partial",
                    "detail": decision.reason,
                },
            )
        else:
            training["adapter"] = None
            self._append_pipeline_stage(
                run_id,
                {
                    "stage": "adapter_register",
                    "status": "blocked",
                    "detail": decision.reason,
                },
            )

        merged = dict(result)
        merged["training"] = training
        return merged

    def training_dashboard(self, *, limit: int = 10) -> dict[str, object]:
        safe_limit = max(1, min(limit, 50))
        runs = self.list_stage1_pipeline_runs(limit=safe_limit)
        datasets = sorted(self.datasets_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        latest_dataset = datasets[0].name if datasets else None
        eval_trend: list[dict[str, object]] = []
        if self.eval_report_file_path.exists():
            lines = self.eval_report_file_path.read_text(encoding="utf-8").splitlines()
            for line in lines[-safe_limit:]:
                if not line.strip():
                    continue
                try:
                    report = json.loads(line)
                except json.JSONDecodeError:
                    continue
                eval_trend.append(
                    {
                        "run_id": report.get("run_id"),
                        "pass_rate": report.get("pass_rate"),
                        "total": report.get("total"),
                        "timestamp": report.get("timestamp"),
                    }
                )
        signal_count = 0
        signal_path = self._training_signal_store.file_path
        if signal_path.exists():
            signal_count = sum(1 for line in signal_path.read_text(encoding="utf-8").splitlines() if line.strip())

        return {
            "stage1_runs": runs[:safe_limit],
            "latest_dataset": latest_dataset,
            "datasets_count": len(datasets),
            "training_signals_count": signal_count,
            "eval_trend": list(reversed(eval_trend)),
            "regression_gate_enabled": self._regression_gate_enabled,
            "shadow_traffic_percent": self._shadow_traffic_percent,
            "tuning_report": self.tuning_report(),
        }

    def tuning_report(self, *, event_limit: int = 5000) -> dict[str, object]:
        return build_tool_loop_tuning_report(
            agent_run_sqlite_path=self.agent_run_sqlite_path,
            training_signals_path=self._training_signal_store.file_path,
            event_limit=event_limit,
        )

    def apply_tuning_recommendations(self, project_id: str) -> dict[str, object]:
        from app.services.project_rules_store import ProjectRulesStore

        report = self.tuning_report()
        recommendations = [
            str(item).strip()
            for item in report.get("recommendations", [])
            if str(item).strip()
        ]
        if not recommendations:
            return {"applied": False, "recommendations": [], "detail": "No recommendations."}

        store = ProjectRulesStore()
        current = store.get_rules(project_id)
        block = "\n".join(f"- {item}" for item in recommendations)
        marker = "[Tool loop tuning]"
        existing = str(current.get("project_rules", "")).strip()
        if marker in existing:
            head, _, _tail = existing.partition(marker)
            merged = f"{head.strip()}\n\n{marker}\n{block}".strip()
        else:
            merged = f"{existing}\n\n{marker}\n{block}".strip() if existing else f"{marker}\n{block}"
        store.save_rules(
            project_id,
            project_rules=merged,
            user_rules=str(current.get("user_rules", "")),
            skills=list(current.get("skills", [])) if isinstance(current.get("skills"), list) else [],
        )
        return {
            "applied": True,
            "project_id": project_id,
            "recommendations": recommendations,
            "detail": f"Appended {len(recommendations)} tuning notes to project rules.",
        }

    @staticmethod
    def _count_sources(samples: list[dict[str, str]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in samples:
            source = str(row.get("source", "unknown"))
            counts[source] = counts.get(source, 0) + 1
        return counts

    def _apply_eval_passed_boost(self, samples: list[dict[str, str]]) -> list[dict[str, str]]:
        passed_refs = self._load_eval_passed_refs()
        if not passed_refs:
            return samples
        boosted: list[dict[str, str]] = []
        for row in samples:
            updated = dict(row)
            task_id = str(updated.get("task_id", "")).strip()
            run_id = str(updated.get("run_id", "")).strip()
            if (task_id and task_id in passed_refs) or (run_id and run_id in passed_refs):
                updated["eval_passed"] = "1"
            boosted.append(updated)
        return boosted

    def _load_eval_passed_refs(self) -> set[str]:
        if not self.eval_report_file_path.exists():
            return set()
        refs: set[str] = set()
        for line in self.eval_report_file_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                report = json.loads(line)
            except json.JSONDecodeError:
                continue
            results = report.get("results")
            if not isinstance(results, list):
                continue
            for item in results:
                if not isinstance(item, dict):
                    continue
                if str(item.get("status", "")) != "passed":
                    continue
                execution_ref = item.get("execution_ref")
                if execution_ref:
                    refs.add(str(execution_ref))
        return refs

    @property
    def training_signal_store(self) -> TrainingSignalStore:
        return self._training_signal_store

    def distill_with_teacher(
        self,
        *,
        name: str,
        limit: int,
        min_samples: int,
        llm_caller,
        teacher_model: str = "",
        teacher_fallback_model: str = "",
        cloud_teacher_model: str = "",
    ) -> dict[str, object]:
        from app.services.teacher_distillation_service import TeacherDistillationService

        samples = self._training_signal_store.load_samples(limit)
        if not samples:
            samples = self._load_agent_run_samples(limit, include_trajectory=True)
        distiller = TeacherDistillationService(
            teacher_model=teacher_model,
            teacher_fallback_model=teacher_fallback_model,
            cloud_teacher_model=cloud_teacher_model,
            datasets_dir=str(self.datasets_dir),
            llm_caller=llm_caller,
            max_samples=limit,
        )
        result = distiller.distill_samples(samples, name=name)
        if result.sample_count < min_samples:
            raise ValueError(
                f"Teacher distillation produced {result.sample_count} samples; "
                f"minimum required is {min_samples}."
            )
        return result.as_dict()

    def export_training_signals_dataset(
        self,
        *,
        name: str = "stage1-signals-export",
        limit: int = 500,
        min_samples: int = 10,
    ) -> dict[str, object]:
        return self.export_dataset(
            FinetuneDatasetExportRequest(
                name=name,
                include_feedback=True,
                include_tasks=True,
                include_agent_runs=True,
                include_training_signals=True,
                include_dpo_negatives=True,
                include_trajectory=True,
                curate_deduplicate=True,
                curate_stratified_balance=True,
                limit=limit,
                min_samples=min_samples,
            )
        )

    def _append_pipeline_stage(self, run_id: str, stage: dict[str, str]) -> None:
        self._update_pipeline_run(run_id, append_stage=stage)

    @staticmethod
    def normalize_stage1_request(payload: FinetuneStage1RunRequest) -> FinetuneStage1RunRequest:
        from app.core.model_roles import resolve_stage1_base_model
        from app.state import get_settings

        resolved = resolve_stage1_base_model(get_settings(), payload.base_model)
        if resolved == payload.base_model:
            return payload
        return payload.model_copy(update={"base_model": resolved})

    def training_recipe(self, base_model: str) -> dict[str, object]:
        return {
            "base_model": base_model,
            "recommended_trainers": [
                "ollama create <name> -f Modelfile",
                "huggingface/peft LoRA",
                "unsloth",
            ],
            "modelfile_template": (
                f"FROM {base_model.split(':', 1)[-1] if ':' in base_model else base_model}\n"
                "PARAMETER temperature 0.2\n"
                "SYSTEM You are the local Termit orchestrator runtime for this repository."
            ),
            "dataset_format": {
                "instruction": "task description",
                "input": "optional context",
                "output": "expected assistant response",
                "source": "feedback|task|agent_run",
            },
        }

    def run_stage1_pipeline(
        self,
        payload: FinetuneStage1RunRequest,
        *,
        baseline_report: Optional[dict[str, object]] = None,
    ) -> dict[str, object]:
        payload = self.normalize_stage1_request(payload)
        stages: list[dict[str, str]] = []
        created_at = datetime.now(timezone.utc).isoformat()
        pipeline_id = f"ftp_{uuid4().hex[:12]}"
        status = "completed"

        export = self.export_dataset(
            FinetuneDatasetExportRequest(
                name=payload.name,
                include_feedback=payload.include_feedback,
                include_tasks=payload.include_tasks,
                include_agent_runs=payload.include_agent_runs,
                include_chat_sessions=True,
                include_trajectory=True,
                min_rating=payload.min_rating,
                min_samples=payload.min_samples,
                limit=payload.limit,
                curate_deduplicate=payload.curate_deduplicate,
                curate_stratified_balance=payload.curate_stratified_balance,
            )
        )
        stages.append(
            {
                "stage": "dataset_export",
                "status": "completed",
                "detail": f"Exported {export['sample_count']} samples to {export['dataset_path']}",
            }
        )

        trajectory_sft: Optional[dict[str, object]] = None
        if payload.export_trajectory_sft:
            try:
                trajectory_sft = self.export_trajectory_sft(
                    FinetuneTrajectoryExportRequest(
                        name=f"{payload.name}-trajectory",
                        limit=min(payload.limit, 300),
                        min_samples=1,
                        success_only=True,
                    )
                )
                stages.append(
                    {
                        "stage": "trajectory_sft_export",
                        "status": "completed",
                        "detail": (
                            f"Exported {trajectory_sft['sample_count']} trajectory SFT rows "
                            f"to {trajectory_sft['dataset_path']}"
                        ),
                    }
                )
            except ValueError as exc:
                stages.append(
                    {
                        "stage": "trajectory_sft_export",
                        "status": "skipped",
                        "detail": str(exc)[:300],
                    }
                )

        if payload.run_eval_baseline and baseline_report is not None:
            pass_rate = float(baseline_report.get("pass_rate", 0.0))
            total = int(baseline_report.get("total", 0))
            stages.append(
                {
                    "stage": "baseline_eval",
                    "status": "completed",
                    "detail": f"Baseline pass rate {pass_rate:.2%} on {total} scenarios",
                }
            )
        elif payload.run_eval_baseline:
            status = "partial"
            stages.append(
                {
                    "stage": "baseline_eval",
                    "status": "skipped",
                    "detail": "Baseline eval requested but no report was provided.",
                }
            )

        job = self.create_job(
            name=payload.name,
            dataset_path=str(export["dataset_path"]),
            sample_count=int(export["sample_count"]),
            base_model=payload.base_model,
            notes=payload.notes,
        )
        stages.append(
            {
                "stage": "job_create",
                "status": "completed",
                "detail": f"Created finetune job {job.job_id}",
            }
        )

        completed_job = self.run_job(job.job_id)
        stages.append(
            {
                "stage": "job_validate",
                "status": "completed",
                "detail": f"Job {completed_job.job_id} validated and marked ready.",
            }
        )

        recipe = self.training_recipe(payload.base_model)
        stages.append(
            {
                "stage": "training_recipe",
                "status": "completed",
                "detail": "Generated trainer and Modelfile recipe.",
            }
        )

        adapter: Optional[dict[str, object]] = None
        if payload.auto_register_adapter:
            if not payload.adapter_name or not payload.adapter_model:
                status = "partial"
                stages.append(
                    {
                        "stage": "adapter_register",
                        "status": "skipped",
                        "detail": "auto_register_adapter=true requires adapter_name and adapter_model.",
                    }
                )
            else:
                adapter = self.register_adapter(
                    FinetuneAdapterRegisterRequest(
                        name=payload.adapter_name,
                        model=payload.adapter_model,
                        base_model=payload.base_model,
                        repo_profile_id=payload.repo_profile_id,
                        description=payload.adapter_description,
                    )
                )
                stages.append(
                    {
                        "stage": "adapter_register",
                        "status": "completed",
                        "detail": f"Registered adapter {adapter['model']}.",
                    }
                )

        baseline_pass_rate = (
            float(baseline_report["pass_rate"])
            if baseline_report is not None and "pass_rate" in baseline_report
            else None
        )
        baseline_total = (
            int(baseline_report["total"])
            if baseline_report is not None and "total" in baseline_report
            else None
        )
        baseline_passed = (
            int(baseline_report["passed"])
            if baseline_report is not None and "passed" in baseline_report
            else None
        )
        baseline_run_id = (
            str(baseline_report["run_id"])
            if baseline_report is not None and "run_id" in baseline_report
            else None
        )

        return {
            "pipeline_id": pipeline_id,
            "status": status,
            "created_at": created_at,
            "dataset": export,
            "baseline_run_id": baseline_run_id,
            "baseline_pass_rate": baseline_pass_rate,
            "baseline_total": baseline_total,
            "baseline_passed": baseline_passed,
            "job": {
                "job_id": completed_job.job_id,
                "name": completed_job.name,
                "status": completed_job.status,
                "dataset_path": completed_job.dataset_path,
                "sample_count": completed_job.sample_count,
                "base_model": completed_job.base_model,
                "created_at": completed_job.created_at,
                "updated_at": completed_job.updated_at,
                "notes": completed_job.notes,
                "adapter_model": completed_job.adapter_model,
            },
            "recipe": recipe,
            "adapter": adapter,
            "trajectory_sft": trajectory_sft,
            "stages": stages,
        }

    def enqueue_stage1_pipeline(self, payload: FinetuneStage1RunRequest) -> dict[str, object]:
        payload = self.normalize_stage1_request(payload)
        now = datetime.now(timezone.utc).isoformat()
        run = FinetunePipelineRunRecord(
            run_id=f"ftpbg_{uuid4().hex[:12]}",
            status="queued",
            created_at=now,
            updated_at=now,
            cancelled=False,
            request=payload.model_dump(),
            stages=[{"stage": "enqueue", "status": "completed", "detail": "Pipeline queued."}],
        )
        with self._lock:
            runs = self._read_pipeline_runs()
            runs.append(run)
            self._write_pipeline_runs(runs)
        return self._pipeline_run_to_dict(run)

    def list_stage1_pipeline_runs(
        self,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> list[dict[str, object]]:
        with self._lock:
            runs = self._read_pipeline_runs()
        ordered = sorted(runs, key=lambda item: item.created_at, reverse=True)
        if status:
            ordered = [item for item in ordered if item.status == status]
        return [self._pipeline_run_to_dict(item) for item in ordered[: max(1, limit)]]

    def get_stage1_pipeline_run(self, run_id: str) -> Optional[dict[str, object]]:
        with self._lock:
            runs = self._read_pipeline_runs()
        match = next((item for item in runs if item.run_id == run_id), None)
        if match is None:
            return None
        return self._pipeline_run_to_dict(match)

    def recover_stuck_pipeline_runs(
        self,
        *,
        stale_seconds: Optional[int] = None,
        requeue: bool = False,
    ) -> list[dict[str, object]]:
        """Mark long-running pipeline runs as failed so queue slots are freed."""
        timeout = stale_seconds or self._pipeline_stuck_timeout_seconds
        now = datetime.now(timezone.utc)
        recovered: list[dict[str, object]] = []
        with self._lock:
            runs = self._read_pipeline_runs()
            updated: list[FinetunePipelineRunRecord] = []
            for item in runs:
                if item.status != "running" or item.cancelled:
                    updated.append(item)
                    continue
                try:
                    updated_at = datetime.fromisoformat(item.updated_at.replace("Z", "+00:00"))
                except ValueError:
                    updated_at = now
                age_seconds = (now - updated_at).total_seconds()
                if age_seconds < timeout:
                    updated.append(item)
                    continue
                detail = (
                    f"Recovered stuck pipeline after {int(age_seconds)}s "
                    f"(timeout={timeout}s)."
                )
                next_status = "queued" if requeue else "failed"
                recovered_run = FinetunePipelineRunRecord(
                    run_id=item.run_id,
                    status=next_status,
                    created_at=item.created_at,
                    updated_at=now.isoformat(),
                    cancelled=False,
                    request=item.request,
                    result=None if requeue else item.result,
                    error=None if requeue else detail,
                    stages=(item.stages or [])
                    + [
                        {
                            "stage": "recover_stuck",
                            "status": "completed" if requeue else "failed",
                            "detail": detail,
                        }
                    ],
                )
                updated.append(recovered_run)
                recovered.append(
                    {
                        "run_id": item.run_id,
                        "previous_status": "running",
                        "new_status": next_status,
                        "age_seconds": int(age_seconds),
                        "requeued": requeue,
                    }
                )
            if recovered:
                self._write_pipeline_runs(updated)
        return recovered

    def cancel_stage1_pipeline_run(self, run_id: str) -> tuple[bool, str]:
        with self._lock:
            runs = self._read_pipeline_runs()
            run = next((item for item in runs if item.run_id == run_id), None)
            if run is None:
                return False, "not_found"
            if run.status in {"queued", "running"}:
                updated = FinetunePipelineRunRecord(
                    run_id=run.run_id,
                    status="cancelled",
                    created_at=run.created_at,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    cancelled=True,
                    request=run.request,
                    result=run.result,
                    error=run.error,
                    stages=(run.stages or [])
                    + [{"stage": "cancel", "status": "completed", "detail": "Pipeline cancelled by user."}],
                )
                runs = [updated if item.run_id == run_id else item for item in runs]
                self._write_pipeline_runs(runs)
                return True, "cancelled"
            return False, run.status

    def retry_stage1_pipeline_run(self, run_id: str) -> tuple[Optional[dict[str, object]], str]:
        with self._lock:
            runs = self._read_pipeline_runs()
            run = next((item for item in runs if item.run_id == run_id), None)
            if run is None:
                return None, "not_found"
            if run.status != "failed":
                return self._pipeline_run_to_dict(run), run.status
            updated = FinetunePipelineRunRecord(
                run_id=run.run_id,
                status="queued",
                created_at=run.created_at,
                updated_at=datetime.now(timezone.utc).isoformat(),
                cancelled=False,
                request=run.request,
                result=None,
                error=None,
                stages=(run.stages or [])
                + [
                    {
                        "stage": "retry",
                        "status": "completed",
                        "detail": "Run re-queued after failure.",
                    }
                ],
            )
            runs = [updated if item.run_id == run_id else item for item in runs]
            self._write_pipeline_runs(runs)
            return self._pipeline_run_to_dict(updated), "queued"

    def drain_stage1_pipeline_queue(
        self,
        baseline_runner: Optional[Callable[[FinetuneStage1RunRequest], dict[str, object]]] = None,
        *,
        wait: bool = False,
    ) -> None:
        threads: list[Thread] = []
        with self._drain_lock:
            while True:
                claimed = self._claim_next_queued_pipeline_run()
                if claimed is None:
                    break
                thread = Thread(
                    target=self._execute_claimed_pipeline_run,
                    args=(claimed.run_id, baseline_runner),
                    daemon=True,
                )
                thread.start()
                threads.append(thread)
        if wait:
            for thread in threads:
                thread.join()

    def _execute_claimed_pipeline_run(
        self,
        run_id: str,
        baseline_runner: Optional[Callable[[FinetuneStage1RunRequest], dict[str, object]]],
    ) -> None:
        try:
            run = self.get_stage1_pipeline_run(run_id)
            if run is None or run["status"] != "running":
                return
            payload = FinetuneStage1RunRequest(**run["request"])
            baseline_report: Optional[dict[str, object]] = None
            if payload.run_eval_baseline and baseline_runner is not None:
                baseline_report = baseline_runner(payload)
            result = self.run_stage1_pipeline(payload, baseline_report=baseline_report)
            result = self._maybe_auto_train_pipeline(run_id, result, payload)
            self._set_pipeline_run_completed(run_id, result)
        except Exception as exc:  # noqa: BLE001
            self._set_pipeline_run_failed(run_id, str(exc))
        finally:
            self.drain_stage1_pipeline_queue(baseline_runner)

    def _load_feedback_samples(self, min_rating: int) -> list[dict[str, str]]:
        if not self.feedback_file_path.exists():
            return []
        rows: list[dict[str, str]] = []
        for line in self.feedback_file_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            rating = item.get("rating")
            if rating is not None and int(rating) < min_rating:
                continue
            message = str(item.get("message", "")).strip()
            if len(message) < 8:
                continue
            instruction = str(item.get("instruction", "")).strip()
            if not instruction:
                instruction = "Respond to the user request for the Termit project"
            row: dict[str, str] = {
                "instruction": instruction,
                "input": "",
                "output": message,
                "source": "feedback",
                "category": "feedback",
            }
            if rating is not None:
                row["rating"] = str(rating)
            for key in ("session_id", "task_id", "run_id"):
                value = item.get(key)
                if value:
                    row[key] = str(value)
            rows.append(row)
        return rows

    def _load_task_samples(self, limit: int, *, include_trajectory: bool = True) -> list[dict[str, str]]:
        if not self.task_sqlite_path.exists():
            return []
        rows: list[dict[str, str]] = []
        with closing(sqlite3.connect(self.task_sqlite_path)) as conn:
            conn.row_factory = sqlite3.Row
            try:
                result = conn.execute(
                    """
                    SELECT task_id, input, report, state, task_type, error, session_id
                    FROM tasks
                    WHERE state = 'completed' AND report IS NOT NULL AND (error IS NULL OR error = '')
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            except sqlite3.Error:
                return []
            for row in result:
                report = str(row["report"] or "").strip()
                if not report:
                    continue
                instruction = str(row["input"] or "").strip()
                context_parts: list[str] = []
                if include_trajectory:
                    context_parts.extend(
                        self._load_task_event_lines(str(row["task_id"]), conn=conn)
                    )
                sample: dict[str, str] = {
                    "instruction": instruction,
                    "input": "\n".join(context_parts).strip(),
                    "output": report,
                    "source": "task",
                    "category": str(row["task_type"] or "general"),
                    "task_id": str(row["task_id"]),
                }
                session_id = row["session_id"]
                if session_id:
                    sample["session_id"] = str(session_id)
                rows.append(sample)
        return rows

    def _load_task_event_lines(self, task_id: str, conn: Optional[sqlite3.Connection] = None) -> list[str]:
        lines: list[str] = []
        try:
            if conn is not None:
                events = conn.execute(
                    """
                    SELECT event_type, message
                    FROM task_events
                    WHERE task_id = ?
                    ORDER BY id ASC
                    LIMIT 40
                    """,
                    (task_id,),
                ).fetchall()
            else:
                with closing(sqlite3.connect(self.task_sqlite_path)) as local_conn:
                    local_conn.row_factory = sqlite3.Row
                    events = local_conn.execute(
                        """
                        SELECT event_type, message
                        FROM task_events
                        WHERE task_id = ?
                        ORDER BY id ASC
                        LIMIT 40
                        """,
                        (task_id,),
                    ).fetchall()
        except sqlite3.Error:
            return lines
        for event in events:
            message = str(event["message"] or "").strip()
            if not message:
                continue
            event_type = str(event["event_type"] or "event")
            lines.append(f"[{event_type}] {message}")
        return lines

    def _load_agent_run_samples(
        self,
        limit: int,
        *,
        include_trajectory: bool = True,
    ) -> list[dict[str, str]]:
        if not self.agent_run_sqlite_path.exists():
            return []
        rows: list[dict[str, str]] = []
        with closing(sqlite3.connect(self.agent_run_sqlite_path)) as conn:
            conn.row_factory = sqlite3.Row
            try:
                result = conn.execute(
                    """
                    SELECT run_id, agent_id, input, response, state, failure_class, error, session_id
                    FROM agent_runs
                    WHERE state = 'completed'
                      AND response IS NOT NULL
                      AND (error IS NULL OR error = '')
                      AND (failure_class IS NULL OR failure_class = '')
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            except sqlite3.Error:
                return []
            for row in result:
                response = str(row["response"] or "").strip()
                if not response:
                    continue
                instruction = str(row["input"] or "").strip()
                trajectory = ""
                if include_trajectory:
                    trajectory = self._load_agent_run_trajectory(str(row["run_id"]), conn)
                sample: dict[str, str] = {
                    "instruction": instruction,
                    "input": trajectory,
                    "output": response,
                    "source": "agent_run",
                    "category": "agent",
                    "run_id": str(row["run_id"]),
                }
                session_id = row["session_id"]
                if session_id:
                    sample["session_id"] = str(session_id)
                if trajectory:
                    sample["trajectory"] = trajectory
                rows.append(sample)
        return rows

    def _load_agent_run_trajectory(self, run_id: str, conn: sqlite3.Connection) -> str:
        try:
            events = conn.execute(
                """
                SELECT event_type, message
                FROM agent_run_events
                WHERE run_id = ?
                ORDER BY id ASC
                LIMIT 80
                """,
                (run_id,),
            ).fetchall()
        except sqlite3.Error:
            return ""
        lines: list[str] = []
        for event in events:
            message = str(event["message"] or "").strip()
            if not message:
                continue
            event_type = str(event["event_type"] or "event")
            lines.append(f"[{event_type}] {message}")
        return "\n".join(lines).strip()

    def _load_chat_session_samples(self, limit: int) -> list[dict[str, str]]:
        if not self.memory_sqlite_path.exists():
            return []
        rows: list[dict[str, str]] = []
        with closing(sqlite3.connect(self.memory_sqlite_path)) as conn:
            conn.row_factory = sqlite3.Row
            try:
                sessions = conn.execute(
                    """
                    SELECT session_id, COUNT(*) AS message_count
                    FROM session_messages
                    GROUP BY session_id
                    HAVING message_count >= 2
                    ORDER BY MAX(id) DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            except sqlite3.Error:
                return []
            for session in sessions:
                session_id = str(session["session_id"])
                messages = conn.execute(
                    """
                    SELECT role, content
                    FROM session_messages
                    WHERE session_id = ?
                    ORDER BY id ASC
                    LIMIT 80
                    """,
                    (session_id,),
                ).fetchall()
                pair = self._pair_chat_messages(messages)
                if pair is None:
                    continue
                instruction, assistant_output = pair
                rows.append(
                    {
                        "instruction": instruction,
                        "input": "",
                        "output": assistant_output,
                        "source": "chat_session",
                        "category": "chat",
                        "session_id": session_id,
                    }
                )
        return rows

    @staticmethod
    def _pair_chat_messages(messages: list[sqlite3.Row]) -> Optional[tuple[str, str]]:
        last_user: Optional[str] = None
        for message in messages:
            role = str(message["role"] or "").strip().lower()
            content = str(message["content"] or "").strip()
            if not content:
                continue
            if role == "user":
                last_user = content
                continue
            if role == "assistant" and last_user:
                return last_user, content
        return None

    def _read_jobs(self) -> list[FinetuneJobRecord]:
        raw = json.loads(self.jobs_path.read_text(encoding="utf-8"))
        jobs: list[FinetuneJobRecord] = []
        for item in raw.get("jobs", []):
            jobs.append(FinetuneJobRecord(**item))
        return jobs

    def _write_jobs(self, jobs: list[FinetuneJobRecord]) -> None:
        payload = {"jobs": [item.__dict__ for item in jobs]}
        self.jobs_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _read_adapters(self) -> list[dict[str, object]]:
        return json.loads(self.adapters_path.read_text(encoding="utf-8")).get("adapters", [])

    def _write_adapters(self, adapters: list[dict[str, object]]) -> None:
        self.adapters_path.write_text(
            json.dumps({"adapters": adapters}, indent=2),
            encoding="utf-8",
        )

    def _upsert_repo_profile_model(self, profile_id: str, model: str) -> None:
        profiles_path = self.repo_profiles_path
        if not profiles_path.exists():
            return
        raw = json.loads(profiles_path.read_text(encoding="utf-8"))
        updated = False
        for item in raw:
            if str(item.get("profile_id")) == profile_id:
                item["preferred_model"] = model
                item["finetuned"] = True
                updated = True
                break
        if updated:
            profiles_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    def _upsert_repo_profile_shadow(
        self,
        profile_id: str,
        model: str,
        traffic_percent: float,
    ) -> None:
        profiles_path = self.repo_profiles_path
        if not profiles_path.exists():
            return
        raw = json.loads(profiles_path.read_text(encoding="utf-8"))
        updated = False
        for item in raw:
            if str(item.get("profile_id")) == profile_id:
                item["shadow_model"] = model
                item["shadow_traffic_percent"] = traffic_percent
                item["finetuned"] = True
                updated = True
                break
        if updated:
            profiles_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    def _read_pipeline_runs(self) -> list[FinetunePipelineRunRecord]:
        raw = json.loads(self.pipelines_path.read_text(encoding="utf-8"))
        items: list[FinetunePipelineRunRecord] = []
        for item in raw.get("runs", []):
            items.append(FinetunePipelineRunRecord(**item))
        return items

    def _write_pipeline_runs(self, runs: list[FinetunePipelineRunRecord]) -> None:
        payload = {"runs": [item.__dict__ for item in runs]}
        self.pipelines_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _pipeline_run_to_dict(item: FinetunePipelineRunRecord) -> dict[str, object]:
        return {
            "run_id": item.run_id,
            "status": item.status,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "cancelled": item.cancelled,
            "request": item.request,
            "result": item.result,
            "error": item.error,
            "stages": item.stages or [],
        }

    @staticmethod
    def _count_running_pipeline_runs(runs: list[FinetunePipelineRunRecord]) -> int:
        return sum(1 for item in runs if item.status == "running" and not item.cancelled)

    def _claim_next_queued_pipeline_run(self) -> Optional[FinetunePipelineRunRecord]:
        with self._lock:
            runs = self._read_pipeline_runs()
            if self._count_running_pipeline_runs(runs) >= self._pipeline_max_concurrency:
                return None
            queued = next((item for item in runs if item.status == "queued" and not item.cancelled), None)
            if queued is None:
                return None
            claimed = FinetunePipelineRunRecord(
                run_id=queued.run_id,
                status="running",
                created_at=queued.created_at,
                updated_at=datetime.now(timezone.utc).isoformat(),
                cancelled=False,
                request=queued.request,
                result=queued.result,
                error=None,
                stages=(queued.stages or [])
                + [
                    {
                        "stage": "execute",
                        "status": "running",
                        "detail": "Pipeline execution started.",
                    }
                ],
            )
            runs = [claimed if item.run_id == queued.run_id else item for item in runs]
            self._write_pipeline_runs(runs)
            return claimed

    def _set_pipeline_run_completed(self, run_id: str, result: dict[str, object]) -> None:
        self._update_pipeline_run(
            run_id,
            status="completed",
            result=result,
            append_stage={
                "stage": "complete",
                "status": "completed",
                "detail": "Pipeline execution completed.",
            },
        )

    def _set_pipeline_run_failed(self, run_id: str, error: str) -> None:
        self._update_pipeline_run(
            run_id,
            status="failed",
            error=error,
            append_stage={
                "stage": "failed",
                "status": "failed",
                "detail": error[:500],
            },
        )

    def _update_pipeline_run(
        self,
        run_id: str,
        *,
        status: Optional[str] = None,
        cancelled: Optional[bool] = None,
        result: Optional[dict[str, object]] = None,
        error: Optional[str] = None,
        append_stage: Optional[dict[str, str]] = None,
    ) -> None:
        with self._lock:
            runs = self._read_pipeline_runs()
            updated_runs: list[FinetunePipelineRunRecord] = []
            for item in runs:
                if item.run_id != run_id:
                    updated_runs.append(item)
                    continue
                updated = FinetunePipelineRunRecord(
                    run_id=item.run_id,
                    status=status or item.status,
                    created_at=item.created_at,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    cancelled=item.cancelled if cancelled is None else cancelled,
                    request=item.request,
                    result=item.result if result is None else result,
                    error=item.error if error is None else error,
                    stages=(item.stages or []) + ([append_stage] if append_stage is not None else []),
                )
                updated_runs.append(updated)
            self._write_pipeline_runs(updated_runs)

    def active_pipeline_slots(self) -> dict[str, int]:
        with self._lock:
            runs = self._read_pipeline_runs()
        running = self._count_running_pipeline_runs(runs)
        return {
            "max_concurrency": self._pipeline_max_concurrency,
            "running": running,
            "available": max(0, self._pipeline_max_concurrency - running),
        }
