import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from app.core.config import get_settings
from app.services.daily_improvement_scheduler_service import DailyImprovementSchedulerService
from app.services.daily_improvement_service import DailyImprovementService
from app.services.finetune_service import FinetuneService


class DailyImprovementServiceTests(unittest.TestCase):
    def _build_service(self, root: Path) -> tuple[DailyImprovementService, MagicMock, MagicMock]:
        feedback_path = root / "feedback.jsonl"
        feedback_path.write_text(
            json.dumps({"rating": 5, "message": "Good patch"}) + "\n",
            encoding="utf-8",
        )
        settings = replace(
            get_settings(),
            daily_improvement_agent_id="agt_test_improver",
            daily_improvement_max_agent_runs=2,
            daily_improvement_max_dlq_replay=1,
            daily_improvement_max_eval_fixes=2,
            daily_improvement_eval_probe_limit=5,
            daily_improvement_run_eval_probe=False,
            agent_templates_path=str(root / "agent_templates.json"),
            desktop_north_star_path=str(root / "north_star.json"),
            finetune_datasets_dir=str(root / "datasets"),
            finetune_jobs_path=str(root / "jobs.json"),
            finetune_adapters_path=str(root / "adapters.json"),
            finetune_pipelines_path=str(root / "pipelines.json"),
            feedback_file_path=str(feedback_path),
            task_sqlite_path=str(root / "tasks.db"),
            agent_run_sqlite_path=str(root / "agent_runs.db"),
            finetune_training_signals_path=str(root / "training_signals.jsonl"),
        )
        (root / "agent_templates.json").write_text(
            json.dumps(
                [
                    {
                        "template_id": "fix-ci",
                        "name": "Fix CI",
                        "description": "fix ci",
                        "task_type": "coding",
                        "system_prompt": "Fix CI",
                        "enabled_tools": ["read_file", "search_repo", "apply_patch"],
                        "use_tool_loop": True,
                        "use_retrieval": True,
                    }
                ]
            ),
            encoding="utf-8",
        )
        (root / "north_star.json").write_text(
            json.dumps(
                {
                    "kpi_targets": {"eval_pass_rate_min": 0.75, "tool_loop_completion_rate_min": 0.8},
                    "journeys": [],
                }
            ),
            encoding="utf-8",
        )

        agent_service = MagicMock()
        agent_service.get_agent.return_value = MagicMock(agent_id="agt_test_improver")
        agent_service.list_dlq_runs.return_value = MagicMock(total=1, runs=[])
        agent_service.replay_dlq.return_value = []
        agent_service.create_run.return_value = MagicMock(run_id="arun_test", state=MagicMock(value="queued"))

        eval_service = MagicMock()
        eval_service.build_dashboard.return_value = {
            "pass_rate": 0.5,
            "recent_reports": [
                {
                    "results": [
                        {
                            "status": "failed",
                            "scenario_id": "patch_basic",
                            "category": "patch",
                            "message": "Patch did not apply",
                            "prompt": "Apply a patch",
                        }
                    ]
                }
            ],
        }
        eval_service.run_suite.return_value = {
            "run_id": "eval_test",
            "pass_rate": 0.5,
            "total": 1,
        }

        kpi_gate_service = MagicMock()
        kpi_gate_service.evaluate_gates.return_value = {
            "overall_passed": False,
            "gates": [
                {
                    "gate_id": "eval_pass_rate",
                    "label": "Eval pass rate",
                    "actual": 0.5,
                    "target": 0.75,
                    "passed": False,
                }
            ],
        }

        finetune_service = FinetuneService(
            datasets_dir=settings.finetune_datasets_dir,
            jobs_path=settings.finetune_jobs_path,
            adapters_path=settings.finetune_adapters_path,
            pipelines_path=settings.finetune_pipelines_path,
            feedback_file_path=settings.feedback_file_path,
            task_sqlite_path=settings.task_sqlite_path,
            agent_run_sqlite_path=settings.agent_run_sqlite_path,
            training_signals_path=settings.finetune_training_signals_path,
        )

        service = DailyImprovementService(
            settings=settings,
            agent_service=agent_service,
            eval_service=eval_service,
            kpi_gate_service=kpi_gate_service,
            finetune_service=finetune_service,
        )
        return service, agent_service, eval_service

    def test_build_plan_prioritizes_dlq_and_eval_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, _, _ = self._build_service(Path(tmp))
            plan = service.build_plan()
            action_types = [item["type"] for item in plan["actions"]]
            self.assertIn("replay_dlq", action_types)
            self.assertIn("agent_run", action_types)
            self.assertIn("eval_probe", action_types)
            self.assertLessEqual(
                sum(1 for item in action_types if item == "agent_run"),
                service._settings.daily_improvement_max_agent_runs,
            )

    def test_execute_plan_enqueues_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            service, agent_service, _ = self._build_service(Path(tmp))
            plan = service.build_plan()
            result = service.execute_plan(plan, source="test")
            self.assertEqual(result["status"], "executed")
            self.assertEqual(result["agent_id"], "agt_test_improver")
            self.assertTrue(agent_service.replay_dlq.called or agent_service.create_run.called)


class DailyImprovementSchedulerTests(unittest.TestCase):
    def test_should_run_for_time_blocks_duplicate_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = replace(
                get_settings(),
                daily_improvement_enabled=True,
                daily_improvement_hour=2,
                daily_improvement_minute=0,
                daily_improvement_state_path=str(root / "state.json"),
                daily_improvement_run_eval_probe=False,
            )
            improvement_service = MagicMock()
            improvement_service.build_plan.return_value = {
                "actions": [{"type": "eval_probe", "priority": 1, "limit": 1, "reason": "probe"}],
                "action_count": 1,
            }
            improvement_service.execute_plan.return_value = {
                "status": "executed",
                "source": "builtin_scheduler",
                "results": [],
            }
            scheduler = DailyImprovementSchedulerService(
                settings=settings,
                improvement_service=improvement_service,
            )
            moment = datetime(2026, 6, 3, 2, 0, tzinfo=timezone.utc)
            self.assertTrue(scheduler.should_run_for_time(moment))
            scheduler._write_state({"slot": "2026-06-03"})
            self.assertFalse(scheduler.should_run_for_time(moment))

    def test_trigger_now_executes_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = replace(
                get_settings(),
                daily_improvement_enabled=True,
                daily_improvement_state_path=str(root / "state.json"),
            )
            improvement_service = MagicMock()
            improvement_service.build_plan.return_value = {
                "actions": [],
                "action_count": 0,
            }
            scheduler = DailyImprovementSchedulerService(
                settings=settings,
                improvement_service=improvement_service,
            )
            result = scheduler.trigger_now()
            self.assertEqual(result["status"], "skipped")
            improvement_service.build_plan.assert_called_once()


if __name__ == "__main__":
    unittest.main()
