import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import FinetuneAdapterRegisterRequest, FinetuneDatasetExportRequest
from app.services.finetune_service import FinetuneService


class FinetuneServiceTests(unittest.TestCase):
    def _build_service(self, root: Path) -> FinetuneService:
        feedback_path = root / "feedback.jsonl"
        feedback_path.write_text(
            json.dumps({"rating": 5, "message": "Great routing suggestion"}) + "\n",
            encoding="utf-8",
        )
        task_db = root / "tasks.db"
        with sqlite3.connect(task_db) as conn:
            conn.execute(
                """
                CREATE TABLE tasks (
                    task_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    input TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    session_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    report TEXT,
                    error TEXT,
                    failure_class TEXT,
                    attempts INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO tasks(
                    task_id, state, input, task_type, mode, session_id,
                    created_at, updated_at, report, error, failure_class,
                    attempts, max_attempts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "t1",
                    "completed",
                    "Add health endpoint",
                    "coding",
                    "auto",
                    None,
                    "2026-05-30T00:00:00Z",
                    "2026-05-30T00:01:00Z",
                    "Implemented GET /health",
                    None,
                    None,
                    1,
                    2,
                ),
            )
            conn.commit()
        agent_db = root / "agent_runs.db"
        with sqlite3.connect(agent_db) as conn:
            conn.execute(
                """
                CREATE TABLE agent_runs (
                    run_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    input TEXT NOT NULL,
                    session_id TEXT,
                    provider TEXT,
                    model TEXT,
                    attempts INTEGER NOT NULL,
                    max_attempts INTEGER NOT NULL,
                    failure_class TEXT,
                    attempted_models TEXT NOT NULL,
                    response TEXT NOT NULL,
                    error TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO agent_runs(
                    run_id, agent_id, agent_name, state, created_at, updated_at,
                    input, session_id, provider, model, attempts, max_attempts,
                    failure_class, attempted_models, response, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "r1",
                    "a1",
                    "Reviewer",
                    "completed",
                    "2026-05-30T00:00:00Z",
                    "2026-05-30T00:02:00Z",
                    "Review auth middleware",
                    None,
                    "ollama",
                    "deepseek-coder",
                    1,
                    2,
                    None,
                    "[]",
                    "Auth middleware uses constant-time compare.",
                    None,
                ),
            )
            conn.commit()
        profiles_path = root / "repo_model_profiles.json"
        profiles_path.write_text(
            json.dumps(
                [
                    {
                        "profile_id": "termit-core",
                        "title": "Core",
                        "path_prefix": "app/",
                        "task_type": "coding",
                        "preferred_model": "ollama:deepseek-coder",
                        "description": "",
                    }
                ]
            ),
            encoding="utf-8",
        )
        return FinetuneService(
            datasets_dir=str(root / "datasets"),
            jobs_path=str(root / "jobs.json"),
            adapters_path=str(root / "adapters.json"),
            feedback_file_path=str(feedback_path),
            task_sqlite_path=str(task_db),
            agent_run_sqlite_path=str(agent_db),
            repo_profiles_path=str(profiles_path),
        )

    def test_export_dataset_from_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(Path(tmp))
            result = service.export_dataset(
                FinetuneDatasetExportRequest(name="termit-beta", min_samples=2)
            )
            self.assertGreaterEqual(result["sample_count"], 2)
            dataset_path = Path(str(result["dataset_path"]))
            self.assertTrue(dataset_path.exists())

    def test_job_lifecycle_and_adapter_registration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._build_service(root)
            export = service.export_dataset(
                FinetuneDatasetExportRequest(name="job-test", min_samples=1)
            )
            job = service.create_job(
                name="job-test",
                dataset_path=str(export["dataset_path"]),
                sample_count=int(export["sample_count"]),
                base_model="ollama:deepseek-coder",
            )
            self.assertEqual(job.status, "queued")
            completed = service.run_job(job.job_id)
            self.assertEqual(completed.status, "completed")

            profiles_path = root / "repo_model_profiles.json"
            adapter = service.register_adapter(
                FinetuneAdapterRegisterRequest(
                    name="termit-core-ft",
                    model="ollama:termit-core-ft",
                    base_model="ollama:deepseek-coder",
                    repo_profile_id="termit-core",
                    description="MVP adapter",
                )
            )
            self.assertTrue(adapter["adapter_id"])
            profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
            self.assertEqual(profiles[0]["preferred_model"], "ollama:termit-core-ft")
            self.assertTrue(profiles[0]["finetuned"])

    def test_training_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(Path(tmp))
            recipe = service.training_recipe("ollama:deepseek-coder")
            self.assertIn("modelfile_template", recipe)
            self.assertIn("ollama create", recipe["recommended_trainers"][0])
