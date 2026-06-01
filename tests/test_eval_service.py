import tempfile
import unittest
from pathlib import Path

from app.services.browser_workflow_service import BrowserWorkflowService
from app.services.eval_report_store import EvalReportStore
from app.services.eval_service import EvalService
from app.services.task_store import InMemoryTaskStore
from app.services.task_service import TaskService
from app.services.tooling_service import ToolingService


class _RetrievalStub:
    def search(self, query: str, *, limit: int = 5, path_prefix: str = ""):
        del query, limit, path_prefix
        from types import SimpleNamespace

        return [SimpleNamespace(path="app/middleware/auth_quota.py")]


class EvalServiceTests(unittest.TestCase):
    def _build_service(self, scenarios_path: str, report_path: str) -> EvalService:
        tooling = ToolingService(root_path=".")
        tasks = TaskService(tooling, InMemoryTaskStore(), max_attempts=2)
        return EvalService(
            scenarios_path=scenarios_path,
            task_service=tasks,
            tooling_service=tooling,
            report_store=EvalReportStore(report_path),
            retrieval_service=_RetrievalStub(),
        )

    def test_lists_49_scenarios_from_file(self) -> None:
        service = self._build_service("./data/eval_scenarios.json", "./data/test_eval_reports.jsonl")
        scenarios = service.list_scenarios()
        self.assertEqual(len(scenarios), 49)

    def test_run_coding_scenario_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = str(Path(tmp) / "reports.jsonl")
            service = self._build_service("./data/eval_scenarios.json", report_path)
            result = service.run_scenario("A1")
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["task_success"], 1)

    def test_run_web_blocker_scenario_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = str(Path(tmp) / "reports.jsonl")
            service = self._build_service("./data/eval_scenarios.json", report_path)
            result = service.run_scenario("W3")
            self.assertEqual(result["status"], "passed")

    def test_run_suite_persists_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = str(Path(tmp) / "reports.jsonl")
            service = self._build_service("./data/eval_scenarios.json", report_path)
            report = service.run_suite(category="coding", limit=3, persist_report=True)
            self.assertEqual(report["total"], 3)
            self.assertEqual(report["passed"], 3)
            self.assertGreater(report["pass_rate"], 0.9)
            stored = service.list_reports(limit=5)
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0]["run_id"], report["run_id"])

    def test_run_patch_scenarios_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = str(Path(tmp) / "reports.jsonl")
            service = self._build_service("./data/eval_scenarios.json", report_path)
            for scenario_id in ("C1", "C2", "C3", "C4", "C5", "C6", "C8", "C9", "C12"):
                result = service.run_scenario(scenario_id)
                self.assertEqual(result["status"], "passed", msg=scenario_id)

    def test_run_new_coding_task_scenarios_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = str(Path(tmp) / "reports.jsonl")
            service = self._build_service("./data/eval_scenarios.json", report_path)
            for scenario_id in ("C6", "C7", "C10", "C11", "C13"):
                result = service.run_scenario(scenario_id)
                self.assertEqual(result["status"], "passed", msg=scenario_id)

    def test_web_scenarios_pass_with_injected_browser_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = str(Path(tmp) / "reports.jsonl")
            tooling = ToolingService(root_path=".")
            tasks = TaskService(tooling, InMemoryTaskStore(), max_attempts=2)
            service = EvalService(
                scenarios_path="./data/eval_scenarios.json",
                task_service=tasks,
                tooling_service=tooling,
                browser_service=BrowserWorkflowService(),
                report_store=EvalReportStore(report_path),
                retrieval_service=_RetrievalStub(),
            )
            for scenario_id in ("W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"):
                result = service.run_scenario(scenario_id)
                self.assertEqual(result["status"], "passed", msg=scenario_id)

    def test_run_tool_sequence_scenarios_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = str(Path(tmp) / "reports.jsonl")
            service = self._build_service("./data/eval_scenarios.json", report_path)
            for scenario_id in ("M1", "M2", "M3", "M8"):
                result = service.run_scenario(scenario_id)
                self.assertEqual(result["status"], "passed", msg=scenario_id)

    def test_run_eval20_scenarios_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = str(Path(tmp) / "reports.jsonl")
            service = self._build_service("./data/eval_scenarios.json", report_path)
            for scenario_id in ("M4", "M5", "M6", "M7"):
                result = service.run_scenario(scenario_id)
                self.assertEqual(result["status"], "passed", msg=scenario_id)

    def test_full_suite_all_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_path = str(Path(tmp) / "reports.jsonl")
            service = self._build_service("./data/eval_scenarios.json", report_path)
            report = service.run_suite(persist_report=False)
            self.assertEqual(report["total"], 49)
            self.assertEqual(report["failed"], 0)
            self.assertEqual(report["pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
