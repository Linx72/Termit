from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Callable, Optional
from uuid import uuid4

from app.domain.schemas import (
    FinetuneAdapterRegisterRequest,
    FinetuneDatasetExportRequest,
    FinetuneStage1RunRequest,
)
from app.services.finetune_trainer_service import FinetuneTrainerService


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
        repo_profiles_path: str = "./data/repo_model_profiles.json",
        pipelines_path: str = "./data/finetune/pipelines.json",
        pipeline_max_concurrency: int = 1,
        trainer: Optional[FinetuneTrainerService] = None,
        auto_train_after_pipeline: bool = False,
        auto_register_after_train: bool = False,
    ) -> None:
        self.datasets_dir = Path(datasets_dir)
        self.jobs_path = Path(jobs_path)
        self.adapters_path = Path(adapters_path)
        self.feedback_file_path = Path(feedback_file_path)
        self.task_sqlite_path = Path(task_sqlite_path)
        self.agent_run_sqlite_path = Path(agent_run_sqlite_path)
        self.repo_profiles_path = Path(repo_profiles_path)
        self.pipelines_path = Path(pipelines_path)
        self._pipeline_max_concurrency = max(1, pipeline_max_concurrency)
        self._trainer = trainer
        self._auto_train_after_pipeline = auto_train_after_pipeline
        self._auto_register_after_train = auto_register_after_train
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
        samples: list[dict[str, str]] = []
        if payload.include_feedback:
            samples.extend(self._load_feedback_samples(payload.min_rating))
        if payload.include_tasks:
            samples.extend(self._load_task_samples(payload.limit))
        if payload.include_agent_runs:
            samples.extend(self._load_agent_run_samples(payload.limit))

        if len(samples) < payload.min_samples:
            raise ValueError(
                f"Dataset has {len(samples)} samples; minimum required is {payload.min_samples}."
            )

        slug = payload.name.strip().replace(" ", "_").lower()[:40] or "dataset"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dataset_path = self.datasets_dir / f"{slug}_{timestamp}.jsonl"
        with dataset_path.open("w", encoding="utf-8") as handle:
            for row in samples:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

        return {
            "name": payload.name,
            "dataset_path": str(dataset_path),
            "sample_count": len(samples),
            "format": "jsonl",
            "fields": ["instruction", "input", "output", "source"],
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
        adapter = {
            "adapter_id": f"fta_{uuid4().hex[:10]}",
            "name": payload.name,
            "model": payload.model,
            "base_model": payload.base_model,
            "repo_profile_id": payload.repo_profile_id,
            "description": payload.description,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            adapters = self._read_adapters()
            adapters.append(adapter)
            self._write_adapters(adapters)
            if payload.repo_profile_id:
                self._upsert_repo_profile_model(payload.repo_profile_id, payload.model)
        return adapter

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
    ) -> dict[str, object]:
        if self._trainer is None:
            raise ValueError("Finetune trainer is not configured.")
        job = self.get_job(job_id)
        if job is None:
            raise ValueError(f"Unknown finetune job: {job_id}")
        train_result = self._trainer.train_dataset(
            dataset_path=job.dataset_path,
            base_model=base_model or job.base_model,
            output_model=output_model,
            trainer_mode=trainer_mode,
            job_id=job.job_id,
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
        train_payload = self.train_job(
            job_id,
            output_model=output_model,
            trainer_mode=trainer_mode,
            auto_register_adapter=auto_register_adapter or request.auto_register_adapter,
            adapter_name=adapter_name or request.adapter_name,
            adapter_model=adapter_model or request.adapter_model,
            base_model=str(job_info.get("base_model") or request.base_model),
            repo_profile_id=repo_profile_id or request.repo_profile_id,
            adapter_description=adapter_description or request.adapter_description,
        )
        train_payload["run_id"] = run_id
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

    def _append_pipeline_stage(self, run_id: str, stage: dict[str, str]) -> None:
        self._update_pipeline_run(run_id, append_stage=stage)

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
                "SYSTEM You are a domain-specific coding assistant for this repository."
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
                min_rating=payload.min_rating,
                min_samples=payload.min_samples,
                limit=payload.limit,
            )
        )
        stages.append(
            {
                "stage": "dataset_export",
                "status": "completed",
                "detail": f"Exported {export['sample_count']} samples to {export['dataset_path']}",
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
            "stages": stages,
        }

    def enqueue_stage1_pipeline(self, payload: FinetuneStage1RunRequest) -> dict[str, object]:
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

    def cancel_stage1_pipeline_run(self, run_id: str) -> tuple[bool, str]:
        with self._lock:
            runs = self._read_pipeline_runs()
            run = next((item for item in runs if item.run_id == run_id), None)
            if run is None:
                return False, "not_found"
            if run.status == "queued":
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
            rows.append(
                {
                    "instruction": "Improve Termit based on user feedback",
                    "input": "",
                    "output": message,
                    "source": "feedback",
                }
            )
        return rows

    def _load_task_samples(self, limit: int) -> list[dict[str, str]]:
        if not self.task_sqlite_path.exists():
            return []
        rows: list[dict[str, str]] = []
        with sqlite3.connect(self.task_sqlite_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                result = conn.execute(
                    """
                    SELECT input, report, state
                    FROM tasks
                    WHERE state = 'completed' AND report IS NOT NULL
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
            rows.append(
                {
                    "instruction": str(row["input"] or ""),
                    "input": "",
                    "output": report,
                    "source": "task",
                }
            )
        return rows

    def _load_agent_run_samples(self, limit: int) -> list[dict[str, str]]:
        if not self.agent_run_sqlite_path.exists():
            return []
        rows: list[dict[str, str]] = []
        with sqlite3.connect(self.agent_run_sqlite_path) as conn:
            conn.row_factory = sqlite3.Row
            try:
                result = conn.execute(
                    """
                    SELECT input, response, status
                    FROM agent_runs
                    WHERE status = 'completed' AND response IS NOT NULL
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
            rows.append(
                {
                    "instruction": str(row["input"] or ""),
                    "input": "",
                    "output": response,
                    "source": "agent_run",
                }
            )
        return rows

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
