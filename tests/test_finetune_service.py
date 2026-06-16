import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app.domain.schemas import (
    FinetuneAdapterRegisterRequest,
    FinetuneDatasetExportRequest,
    FinetuneDpoExportRequest,
    FinetuneStage1RunRequest,
    FinetuneTrajectoryExportRequest,
)
from app.services.finetune_service import FinetuneService
from app.services.finetune_trainer_service import FinetuneTrainerService


class FinetuneServiceTests(unittest.TestCase):
    def _build_service(self, root: Path) -> FinetuneService:
        feedback_path = root / "feedback.jsonl"
        feedback_path.write_text(
            json.dumps(
                {
                    "rating": 5,
                    "message": "Great routing suggestion",
                    "instruction": "Route this coding task",
                    "session_id": "sess-1",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        task_db = root / "tasks.db"
        with closing(sqlite3.connect(task_db)) as conn:
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
            conn.execute(
                """
                CREATE TABLE task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO task_events(task_id, event_type, state, message, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("t1", "plan_ready", "running", "Prepared 3 steps", "2026-05-30T00:00:30Z"),
            )
            conn.commit()
        agent_db = root / "agent_runs.db"
        with closing(sqlite3.connect(agent_db)) as conn:
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
            conn.execute(
                """
                CREATE TABLE agent_run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    attempt INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO agent_run_events(
                    run_id, event_type, state, message, timestamp, attempt
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("r1", "tool_call", "running", "read_file app/core/auth.py", "2026-05-30T00:01:30Z", 1),
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
        signals_path = root / "training_signals.jsonl"
        signals_path.write_text("", encoding="utf-8")
        memory_db = root / "memory.db"
        with closing(sqlite3.connect(memory_db)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        return FinetuneService(
            datasets_dir=str(root / "datasets"),
            jobs_path=str(root / "jobs.json"),
            adapters_path=str(root / "adapters.json"),
            pipelines_path=str(root / "pipelines.json"),
            cycle_events_path=str(root / "stage1_cycle_events.jsonl"),
            feedback_file_path=str(feedback_path),
            task_sqlite_path=str(task_db),
            agent_run_sqlite_path=str(agent_db),
            memory_sqlite_path=str(memory_db),
            training_signals_path=str(signals_path),
            repo_profiles_path=str(profiles_path),
        )

    def test_export_dataset_from_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(Path(tmp))
            result = service.export_dataset(
                FinetuneDatasetExportRequest(name="termit-beta", min_samples=2)
            )
            self.assertGreaterEqual(result["sample_count"], 2)
            self.assertIn("curation", result)
            dataset_path = Path(str(result["dataset_path"]))
            self.assertTrue(dataset_path.exists())
            lines = dataset_path.read_text(encoding="utf-8").strip().splitlines()
            payload = json.loads(lines[0])
            self.assertIn("quality_score", payload)

    def test_export_uses_feedback_instruction_and_trajectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(Path(tmp))
            result = service.export_dataset(
                FinetuneDatasetExportRequest(
                    name="rich-export",
                    min_samples=1,
                    include_chat_sessions=False,
                )
            )
            dataset_path = Path(str(result["dataset_path"]))
            rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
            feedback_rows = [row for row in rows if row.get("source") == "feedback"]
            agent_rows = [row for row in rows if row.get("source") == "agent_run"]
            self.assertTrue(feedback_rows)
            self.assertEqual(feedback_rows[0]["instruction"], "Route this coding task")
            self.assertTrue(agent_rows)
            self.assertIn("read_file", agent_rows[0].get("input", ""))

    def test_export_trajectory_sft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._build_service(root)
            with closing(sqlite3.connect(root / "agent_runs.db")) as conn:
                conn.execute(
                    """
                    INSERT INTO agent_run_events(run_id, event_type, state, message, timestamp, attempt)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "r1",
                        "tool_loop_trace",
                        "running",
                        json.dumps(
                            {
                                "step": 1,
                                "action": "tool",
                                "tool": "read_file",
                                "observation": "middleware source",
                                "assistant": '{"action":"tool","tool":"read_file"}',
                            }
                        ),
                        "2026-05-30T00:01:31Z",
                        1,
                    ),
                )
                conn.commit()
            result = service.export_trajectory_sft(
                FinetuneTrajectoryExportRequest(name="agent-traces", min_samples=1, min_messages=3)
            )
            self.assertEqual(result["format"], "sft_chat_jsonl")
            self.assertGreaterEqual(result["sample_count"], 1)
            row = json.loads(Path(str(result["dataset_path"])).read_text(encoding="utf-8").splitlines()[0])
            self.assertIn("messages", row)

    def test_export_dpo_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._build_service(root)
            from app.services.training_signal_store import TrainingSignalStore

            instruction = "Fix routing for finetune adapter"
            store = TrainingSignalStore(
                str(root / "training_signals.jsonl"),
                min_output_chars=8,
                enabled=True,
            )
            store.try_capture_tool_step(
                run_id="dpo-pos",
                step=1,
                action="tool",
                tool="apply_patch",
                observation="Adapter resolver wired into routing policy successfully.",
                instruction=instruction,
                verified=True,
            )
            store.try_capture_negative_tool_step(
                run_id="dpo-neg",
                step=2,
                action="tool",
                tool="apply_patch",
                observation="Tool error: adapter resolver returned empty model name.",
                instruction=instruction,
                reason="tool_error",
            )
            service._training_signal_store = store
            result = service.export_dpo_dataset(
                FinetuneDpoExportRequest(name="dpo-test", min_pairs=1, min_chosen_chars=8)
            )
            self.assertEqual(result["format"], "dpo_jsonl")
            self.assertGreaterEqual(result["pair_count"], 1)
            self.assertTrue(result["contract_valid"])

    def test_train_dpo_dataset_runs_hf_dpo_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._build_service(root)
            from app.services.training_signal_store import TrainingSignalStore

            instruction = "Fix verify command path"
            store = TrainingSignalStore(
                str(root / "training_signals.jsonl"),
                min_output_chars=8,
                enabled=True,
            )
            store.try_capture_tool_step(
                run_id="dpo-pos-2",
                step=1,
                action="tool",
                tool="apply_patch",
                observation="Use repo root verify command to avoid cwd issues.",
                instruction=instruction,
                verified=True,
            )
            store.try_capture_negative_tool_step(
                run_id="dpo-neg-2",
                step=2,
                action="tool",
                tool="apply_patch",
                observation="verify failed: command executed from wrong directory",
                instruction=instruction,
                reason="verify_failed",
            )
            service._training_signal_store = store
            export = service.export_dpo_dataset(
                FinetuneDpoExportRequest(name="dpo-train", min_pairs=1, min_chosen_chars=8)
            )
            service._trainer = FinetuneTrainerService(
                modelfiles_dir=str(root / "modelfiles"),
                adapters_dir=str(root / "adapters"),
                trainer_mode="hf_dpo",
                hf_dry_run=True,
            )
            train = service.train_dpo_dataset(
                dataset_path=str(export["dataset_path"]),
                base_model="ollama:deepseek-coder",
                output_model="termit-dpo-ft",
                trainer_mode="hf_dpo",
                repo_profile_id="termit-core",
            )
            self.assertEqual(train["status"], "completed")
            self.assertIn("unsloth_dpo_train.py", str(train.get("command", "")))

    def test_export_boosts_eval_passed_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._build_service(root)
            eval_reports = root / "eval_reports.jsonl"
            eval_reports.write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "status": "passed",
                                "execution_ref": "t1",
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            service.eval_report_file_path = eval_reports
            result = service.export_dataset(
                FinetuneDatasetExportRequest(
                    name="eval-boost",
                    min_samples=1,
                    include_feedback=False,
                    include_agent_runs=False,
                    include_chat_sessions=False,
                    include_training_signals=False,
                    prefer_eval_passed=True,
                )
            )
            dataset_path = Path(str(result["dataset_path"]))
            rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
            task_rows = [row for row in rows if row.get("source") == "task"]
            self.assertTrue(task_rows)
            self.assertEqual(task_rows[0].get("eval_passed"), "1")

    def test_export_dedup_preserves_diverse_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._build_service(root)
            signals_path = root / "training_signals.jsonl"
            signals_path.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "instruction": "Implement retry logic",
                            "output": "Use exponential backoff with jitter for HTTP retries",
                            "source": "training_signal",
                            "category": "coding",
                        }
                    )
                    for _ in range(1)
                )
                + "\n"
                + json.dumps(
                    {
                        "instruction": "Implement retry logic",
                        "output": "Wrap requests in tenacity retry decorator with max 3 attempts",
                        "source": "training_signal",
                        "category": "coding",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            service.training_signals_path = signals_path
            from app.services.training_signal_store import TrainingSignalStore

            service._training_signal_store = TrainingSignalStore(str(signals_path), min_output_chars=12)
            result = service.export_dataset(
                FinetuneDatasetExportRequest(
                    name="dedup-diverse",
                    min_samples=2,
                    include_feedback=False,
                    include_tasks=False,
                    include_agent_runs=False,
                    include_chat_sessions=False,
                    include_training_signals=True,
                    curate_deduplicate=True,
                )
            )
            dataset_path = Path(str(result["dataset_path"]))
            rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 2)
            outputs = {row["output"] for row in rows}
            self.assertEqual(len(outputs), 2)

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

    def test_register_adapter_deduplicates_same_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(Path(tmp))
            first = service.register_adapter(
                FinetuneAdapterRegisterRequest(
                    name="termit-core-ft",
                    model="ollama:termit-core-ft",
                    base_model="ollama:deepseek-coder",
                    repo_profile_id="termit-core",
                    description="first",
                )
            )
            second = service.register_adapter(
                FinetuneAdapterRegisterRequest(
                    name="termit-core-ft-v2",
                    model="ollama:termit-core-ft",
                    base_model="ollama:deepseek-coder",
                    repo_profile_id="termit-core",
                    description="updated",
                )
            )
            self.assertEqual(first["adapter_id"], second["adapter_id"])
            adapters = service.list_adapters()
            self.assertEqual(len(adapters), 1)
            self.assertEqual(adapters[0]["description"], "updated")

    def test_shadow_profile_upsert_on_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profiles_path = root / "repo_model_profiles.json"
            profiles_path.write_text(
                json.dumps(
                    [
                        {
                            "profile_id": "termit-core",
                            "title": "Termit core",
                            "path_prefix": "app/",
                            "task_type": "coding",
                            "preferred_model": "ollama:deepseek-coder",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            service = self._build_service(root)
            service._upsert_repo_profile_shadow(
                "termit-core",
                "ollama:shadow-ft",
                15.0,
            )
            profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
            self.assertEqual(profiles[0]["shadow_model"], "ollama:shadow-ft")
            self.assertEqual(profiles[0]["shadow_traffic_percent"], 15.0)
            self.assertTrue(profiles[0]["finetuned"])

    def test_training_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(Path(tmp))
            recipe = service.training_recipe("ollama:deepseek-coder")
            self.assertIn("modelfile_template", recipe)
            self.assertIn("ollama create", recipe["recommended_trainers"][0])

    def test_stage1_pipeline_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(Path(tmp))
            result = service.run_stage1_pipeline(
                FinetuneStage1RunRequest(
                    name="stage1-auto",
                    base_model="ollama:deepseek-coder",
                    min_samples=2,
                    run_eval_baseline=True,
                    auto_register_adapter=True,
                    adapter_name="stage1-auto-ft",
                    adapter_model="ollama:stage1-auto-ft",
                    repo_profile_id="termit-core",
                ),
                baseline_report={
                    "run_id": "eval_123",
                    "pass_rate": 0.75,
                    "total": 24,
                    "passed": 18,
                },
            )

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["baseline_run_id"], "eval_123")
            self.assertEqual(result["job"]["status"], "completed")
            self.assertIsNotNone(result["adapter"])

    def test_stage1_pipeline_queue_and_cancel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(Path(tmp))
            queued = service.enqueue_stage1_pipeline(
                FinetuneStage1RunRequest(
                    name="queued-stage1",
                    base_model="ollama:deepseek-coder",
                    min_samples=1,
                )
            )
            run_id = str(queued["run_id"])
            fetched = service.get_stage1_pipeline_run(run_id)
            self.assertIsNotNone(fetched)
            assert fetched is not None
            self.assertEqual(fetched["status"], "queued")

            cancelled, state = service.cancel_stage1_pipeline_run(run_id)
            self.assertTrue(cancelled)
            self.assertEqual(state, "cancelled")
            after = service.get_stage1_pipeline_run(run_id)
            assert after is not None
            self.assertEqual(after["status"], "cancelled")

    def test_stage1_pipeline_queue_drain_completes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = self._build_service(root)
            queued = service.enqueue_stage1_pipeline(
                FinetuneStage1RunRequest(
                    name="queued-drain",
                    base_model="ollama:deepseek-coder",
                    min_samples=1,
                    run_eval_baseline=True,
                )
            )
            run_id = str(queued["run_id"])

            def baseline_runner(_payload: FinetuneStage1RunRequest) -> dict[str, object]:
                return {
                    "run_id": "eval_queued",
                    "pass_rate": 0.5,
                    "total": 10,
                    "passed": 5,
                }

            service.drain_stage1_pipeline_queue(baseline_runner, wait=True)
            done = service.get_stage1_pipeline_run(run_id)
            assert done is not None
            self.assertEqual(done["status"], "completed")
            self.assertIsNotNone(done["result"])
            dashboard = service.training_dashboard(limit=5)
            self.assertIn("cycle_events", dashboard)
            self.assertGreaterEqual(len(dashboard["cycle_events"]), 1)
            self.assertEqual(dashboard["cycle_events"][0]["status"], "completed")

    def test_stage1_pipeline_list_failed_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(Path(tmp))
            failed_run = service.enqueue_stage1_pipeline(
                FinetuneStage1RunRequest(
                    name="will-fail",
                    base_model="ollama:deepseek-coder",
                    min_samples=999,
                )
            )
            run_id = str(failed_run["run_id"])
            service.drain_stage1_pipeline_queue(None, wait=True)
            done = service.get_stage1_pipeline_run(run_id)
            assert done is not None
            self.assertEqual(done["status"], "failed")

            failed_only = service.list_stage1_pipeline_runs(status="failed")
            self.assertEqual(len(failed_only), 1)
            self.assertEqual(failed_only[0]["run_id"], run_id)

    def test_stage1_pipeline_retry_requeues_failed_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = self._build_service(Path(tmp))
            queued = service.enqueue_stage1_pipeline(
                FinetuneStage1RunRequest(
                    name="retry-me",
                    base_model="ollama:deepseek-coder",
                    min_samples=999,
                )
            )
            run_id = str(queued["run_id"])
            service.drain_stage1_pipeline_queue(None, wait=True)
            failed = service.get_stage1_pipeline_run(run_id)
            assert failed is not None
            self.assertEqual(failed["status"], "failed")

            retried, state = service.retry_stage1_pipeline_run(run_id)
            self.assertEqual(state, "queued")
            assert retried is not None
            self.assertEqual(retried["status"], "queued")
            self.assertIsNone(retried["error"])

            busy, busy_state = service.retry_stage1_pipeline_run(run_id)
            self.assertEqual(busy_state, "queued")

    def test_stage1_pipeline_concurrency_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service = FinetuneService(
                datasets_dir=str(Path(tmp) / "datasets"),
                jobs_path=str(Path(tmp) / "jobs.json"),
                adapters_path=str(Path(tmp) / "adapters.json"),
                pipelines_path=str(Path(tmp) / "pipelines.json"),
                feedback_file_path=str(Path(tmp) / "feedback.jsonl"),
                task_sqlite_path=str(Path(tmp) / "tasks.db"),
                agent_run_sqlite_path=str(Path(tmp) / "agent_runs.db"),
                pipeline_max_concurrency=1,
            )
            service.enqueue_stage1_pipeline(
                FinetuneStage1RunRequest(name="run-a", base_model="ollama:deepseek-coder", min_samples=1)
            )
            service.enqueue_stage1_pipeline(
                FinetuneStage1RunRequest(name="run-b", base_model="ollama:deepseek-coder", min_samples=1)
            )
            first = service._claim_next_queued_pipeline_run()
            assert first is not None
            second = service._claim_next_queued_pipeline_run()
            self.assertIsNone(second)
            slots = service.active_pipeline_slots()
            self.assertEqual(slots["running"], 1)
            self.assertEqual(slots["available"], 0)
