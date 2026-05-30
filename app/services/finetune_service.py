from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional
from uuid import uuid4

from app.domain.schemas import FinetuneAdapterRegisterRequest, FinetuneDatasetExportRequest


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
    ) -> None:
        self.datasets_dir = Path(datasets_dir)
        self.jobs_path = Path(jobs_path)
        self.adapters_path = Path(adapters_path)
        self.feedback_file_path = Path(feedback_file_path)
        self.task_sqlite_path = Path(task_sqlite_path)
        self.agent_run_sqlite_path = Path(agent_run_sqlite_path)
        self.repo_profiles_path = Path(repo_profiles_path)
        self._lock = Lock()
        self.datasets_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_path.parent.mkdir(parents=True, exist_ok=True)
        self.adapters_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.jobs_path.exists():
            self._write_jobs([])
        if not self.adapters_path.exists():
            self._write_adapters([])

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
