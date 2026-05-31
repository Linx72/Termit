from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.domain.schemas import (
    ApplyPatchHunk,
    ApplyPatchRequest,
    ExecuteCommandRequest,
    ListFilesRequest,
    ReadFileRequest,
    TaskCreateRequest,
    TaskMode,
    TaskState,
    TaskType,
    WebAutomationRequest,
)
from app.services.browser_workflow_service import BrowserWorkflowService, WebWorkflowError
from app.services.eval_report_store import EvalReportStore
from app.services.task_service import TaskService
from app.services.telemetry_store import TelemetryStore
from app.services.tooling_service import ToolingError, ToolingService

EVAL_STUB_PAGES: dict[str, tuple[int, str, str]] = {
    "W1": (200, "<html><title>Eval W1</title><body><a href='/docs'>Docs</a></body></html>", "https://eval.stub/w1"),
    "W2": (200, "<html><title>Form</title><body><form><input name='q'/></form></body></html>", "https://eval.stub/w2"),
    "W3": (200, "<html><body>Sign in to continue</body></html>", "https://eval.stub/w3"),
    "W4": (200, "<html><title>Page A</title><body>Version 1</body></html>", "https://eval.stub/w4"),
    "W5": (200, "<html><title>Evidence</title><body>Snapshot target</body></html>", "https://eval.stub/w5"),
    "W6": (200, "<html><body><a href='/api'>API</a><a href='/docs'>Docs</a></body></html>", "https://eval.stub/w6"),
    "W7": (200, "<html><body>Error 500 reproduced in trace</body></html>", "https://eval.stub/w7"),
    "W8": (200, "<html><title>Loop guard</title><body>safe action page</body></html>", "https://eval.stub/w8"),
}


_EVAL_PATCH_FIXTURE = "data/eval_fixtures/patch_sample.txt"
_EVAL_PATCH_BASELINE = "hello world\n"


@dataclass(frozen=True)
class EvalScenario:
    id: str
    category: str
    title: str
    prompt: str
    runner: str
    task_type: str = "coding"
    tool_path: str = "."
    tool_pattern: str = "*"
    tool_command: str = ""
    tool_dry_run: bool = False
    web_url: str = "https://example.com"
    web_max_steps: int = 4
    patch_path: str = ""
    patch_old: str = ""
    patch_new: str = ""
    patch_create: bool = False
    patch_dry_run: bool = True
    patch_confirmed: bool = False
    verify_command: str = ""
    expect_verify_failure: bool = False


class EvalService:
    def __init__(
        self,
        scenarios_path: str = "./data/eval_scenarios.json",
        task_service: Optional[TaskService] = None,
        tooling_service: Optional[ToolingService] = None,
        browser_service: Optional[BrowserWorkflowService] = None,
        telemetry: Optional[TelemetryStore] = None,
        report_store: Optional[EvalReportStore] = None,
        web_fetcher: Optional[Callable[[str, int], tuple[int, str, str]]] = None,
    ) -> None:
        self._scenarios = self._load_scenarios(scenarios_path)
        self._task_service = task_service
        self._tooling = tooling_service
        self._browser = browser_service
        self._telemetry = telemetry
        self._report_store = report_store
        self._web_fetcher = web_fetcher

    def _load_scenarios(self, scenarios_path: str) -> list[EvalScenario]:
        path = Path(scenarios_path)
        if not path.exists():
            return [
                EvalScenario(
                    "A1",
                    "coding",
                    "Implement function",
                    "Implement missing function from docstring.",
                    "task",
                ),
            ]
        raw = json.loads(path.read_text(encoding="utf-8"))
        scenarios: list[EvalScenario] = []
        for item in raw:
            category = str(item["category"])
            runner = str(item.get("runner", self._default_runner(category)))
            scenarios.append(
                EvalScenario(
                    id=str(item["id"]),
                    category=category,
                    title=str(item["title"]),
                    prompt=str(item["prompt"]),
                    runner=runner,
                    task_type=str(item.get("task_type", "coding")),
                    tool_path=str(item.get("tool_path", ".")),
                    tool_pattern=str(item.get("tool_pattern", "*")),
                    tool_command=str(item.get("tool_command", "")),
                    tool_dry_run=bool(item.get("tool_dry_run", False)),
                    web_url=str(item.get("web_url", "https://example.com")),
                    web_max_steps=int(item.get("web_max_steps", 4)),
                    patch_path=str(item.get("patch_path", "")),
                    patch_old=str(item.get("patch_old", "")),
                    patch_new=str(item.get("patch_new", "")),
                    patch_create=bool(item.get("patch_create", False)),
                    patch_dry_run=bool(item.get("patch_dry_run", True)),
                    patch_confirmed=bool(item.get("patch_confirmed", False)),
                    verify_command=str(item.get("verify_command", "")),
                    expect_verify_failure=bool(item.get("expect_verify_failure", False)),
                )
            )
        return scenarios

    @staticmethod
    def _default_runner(category: str) -> str:
        if category == "coding":
            return "task"
        if category == "local":
            return "tool_list"
        return "web"

    def list_scenarios(self) -> list[EvalScenario]:
        return list(self._scenarios)

    def run_scenario(self, scenario_id: str) -> dict[str, object]:
        scenario = self._get_scenario(scenario_id)
        started = time.perf_counter()
        try:
            execution_ref, passed, failure_class, safety_ok, automation = self._execute(scenario)
            status = "passed" if passed else "failed"
            message = "Scenario executed successfully." if passed else "Scenario execution failed."
        except Exception as exc:  # noqa: BLE001 - eval harness captures all runner failures
            execution_ref = None
            passed = False
            failure_class = "tool_error"
            safety_ok = 1
            automation = "manual assisted"
            status = "failed"
            message = str(exc)

        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "scenario_id": scenario.id,
            "category": scenario.category,
            "title": scenario.title,
            "prompt": scenario.prompt,
            "status": status,
            "message": message,
            "task_success": 1 if passed else 0,
            "safety_compliance": safety_ok,
            "automation_level": automation,
            "duration_ms": duration_ms,
            "failure_class": failure_class,
            "execution_ref": execution_ref,
        }

    def run_suite(
        self,
        *,
        category: Optional[str] = None,
        limit: Optional[int] = None,
        persist_report: bool = True,
    ) -> dict[str, object]:
        run_id = f"eval_{uuid4().hex[:12]}"
        started_at = time.time()
        selected = self._scenarios
        if category:
            selected = [item for item in selected if item.category == category]
        if limit is not None:
            selected = selected[: max(0, limit)]

        results: list[dict[str, object]] = []
        for scenario in selected:
            results.append(self.run_scenario(scenario.id))

        passed = sum(1 for item in results if item["status"] == "passed")
        failed = len(results) - passed
        finished_at = time.time()
        metrics = self._telemetry.snapshot() if self._telemetry else None

        report = {
            "run_id": run_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / len(results), 4) if results else 0.0,
            "category_filter": category,
            "results": results,
            "metrics": metrics.model_dump() if metrics else None,
        }
        if persist_report and self._report_store is not None:
            self._report_store.append_suite_report(report)
        return report

    def list_reports(self, limit: int = 10) -> list[dict[str, object]]:
        if self._report_store is None:
            return []
        return self._report_store.list_recent(limit=limit)

    def _get_scenario(self, scenario_id: str) -> EvalScenario:
        scenario = next((item for item in self._scenarios if item.id == scenario_id), None)
        if scenario is None:
            raise ValueError(f"Unknown scenario id: {scenario_id}")
        return scenario

    def _execute(
        self, scenario: EvalScenario
    ) -> tuple[Optional[str], bool, Optional[str], int, str]:
        runner = scenario.runner
        if runner == "task":
            return self._run_task_scenario(scenario)
        if runner == "tool_list":
            return self._run_tool_list(scenario)
        if runner == "tool_read":
            return self._run_tool_read(scenario)
        if runner == "tool_exec":
            return self._run_tool_exec(scenario)
        if runner == "tool_patch":
            return self._run_tool_patch(scenario)
        if runner == "tool_patch_verify":
            return self._run_tool_patch_verify(scenario)
        if runner == "web":
            return self._run_web_scenario(scenario)
        raise ValueError(f"Unsupported runner: {runner}")

    def _run_task_scenario(self, scenario: EvalScenario) -> tuple[str, bool, Optional[str], int, str]:
        if self._task_service is None:
            raise RuntimeError("Task service is not configured for eval runs.")
        task_type = TaskType(scenario.task_type)
        created = self._task_service.create_task(
            TaskCreateRequest(
                input=scenario.prompt,
                task_type=task_type,
                mode=TaskMode.auto,
            )
        )
        task = self._task_service.get_task(created.task_id)
        passed = task.state == TaskState.completed
        failure_class = task.failure_class if not passed else None
        return created.task_id, passed, failure_class, 1, "full-auto"

    def _run_tool_list(self, scenario: EvalScenario) -> tuple[str, bool, Optional[str], int, str]:
        if self._tooling is None:
            raise RuntimeError("Tooling service is not configured for eval runs.")
        listing = self._tooling.list_files(
            ListFilesRequest(path=scenario.tool_path, pattern=scenario.tool_pattern)
        )
        passed = len(listing.files) > 0
        return listing.path, passed, None if passed else "verification_error", 1, "semi-auto"

    def _run_tool_read(self, scenario: EvalScenario) -> tuple[str, bool, Optional[str], int, str]:
        if self._tooling is None:
            raise RuntimeError("Tooling service is not configured for eval runs.")
        content = self._tooling.read_file(ReadFileRequest(path=scenario.tool_path, max_bytes=8000))
        passed = len(content.content.strip()) > 0
        return content.path, passed, None if passed else "verification_error", 1, "semi-auto"

    def _run_tool_exec(self, scenario: EvalScenario) -> tuple[str, bool, Optional[str], int, str]:
        if self._tooling is None:
            raise RuntimeError("Tooling service is not configured for eval runs.")
        if not scenario.tool_command:
            raise ValueError("tool_exec runner requires tool_command.")
        result = self._tooling.execute_command(
            ExecuteCommandRequest(
                command=scenario.tool_command,
                path=scenario.tool_path,
                dry_run=scenario.tool_dry_run,
                confirmed=False,
            )
        )
        blocked = result.risk_level.value == "blocked" and not result.executed
        passed = not blocked and (result.executed or scenario.tool_dry_run)
        failure_class = "safety_block" if blocked else None
        safety_ok = 0 if blocked else 1
        return result.command, passed, failure_class, safety_ok, "semi-auto"

    def _run_tool_patch(self, scenario: EvalScenario) -> tuple[str, bool, Optional[str], int, str]:
        if self._tooling is None:
            raise RuntimeError("Tooling service is not configured for eval runs.")
        if not scenario.patch_path:
            raise ValueError("tool_patch runner requires patch_path.")
        if scenario.patch_path == _EVAL_PATCH_FIXTURE:
            self._reset_patch_fixture()
        hunks = []
        if scenario.patch_old or scenario.patch_new:
            hunks = [ApplyPatchHunk(old_text=scenario.patch_old, new_text=scenario.patch_new)]
        result = self._tooling.apply_patch(
            ApplyPatchRequest(
                path=scenario.patch_path,
                hunks=hunks,
                create=scenario.patch_create,
                dry_run=scenario.patch_dry_run,
                confirmed=scenario.patch_confirmed,
            )
        )
        blocked = result.risk_level.value == "blocked"
        passed = not blocked and (result.applied or scenario.patch_dry_run)
        failure_class = "safety_block" if blocked else None
        safety_ok = 0 if blocked else 1
        return result.path, passed, failure_class, safety_ok, "semi-auto"

    def _run_tool_patch_verify(self, scenario: EvalScenario) -> tuple[str, bool, Optional[str], int, str]:
        if self._tooling is None:
            raise RuntimeError("Tooling service is not configured for eval runs.")
        if not scenario.patch_path:
            raise ValueError("tool_patch_verify runner requires patch_path.")
        if not scenario.verify_command:
            raise ValueError("tool_patch_verify runner requires verify_command.")
        if scenario.patch_path == _EVAL_PATCH_FIXTURE:
            self._reset_patch_fixture()
        hunks = []
        if scenario.patch_old or scenario.patch_new:
            hunks = [ApplyPatchHunk(old_text=scenario.patch_old, new_text=scenario.patch_new)]
        patch_result = self._tooling.apply_patch(
            ApplyPatchRequest(
                path=scenario.patch_path,
                hunks=hunks,
                create=scenario.patch_create,
                dry_run=scenario.patch_dry_run,
                confirmed=scenario.patch_confirmed,
            )
        )
        if patch_result.risk_level.value == "blocked":
            return patch_result.path, False, "safety_block", 0, "semi-auto"
        if not patch_result.applied and not scenario.patch_dry_run:
            return patch_result.path, False, "verification_error", 1, "semi-auto"

        verify_result = self._tooling.execute_command(
            ExecuteCommandRequest(
                command=scenario.verify_command,
                path=scenario.tool_path or ".",
                dry_run=False,
                confirmed=True,
            )
        )
        verify_ok = verify_result.executed and verify_result.exit_code == 0
        if scenario.expect_verify_failure:
            passed = verify_result.executed and verify_result.exit_code != 0
            failure_class = None if passed else "verification_error"
        else:
            passed = verify_ok
            failure_class = None if passed else "verification_error"
        return (
            f"{patch_result.path}|{verify_result.command}",
            passed,
            failure_class,
            1,
            "semi-auto",
        )

    def _reset_patch_fixture(self) -> None:
        if self._tooling is None:
            return
        target = self._tooling.root / _EVAL_PATCH_FIXTURE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_EVAL_PATCH_BASELINE, encoding="utf-8")

    def _run_web_scenario(self, scenario: EvalScenario) -> tuple[str, bool, Optional[str], int, str]:
        url = scenario.web_url
        fetcher = self._web_fetcher or self._eval_stub_fetcher
        browser = self._browser or BrowserWorkflowService(fetcher=fetcher)
        try:
            result = browser.run(
                WebAutomationRequest(
                    url=url,
                    objective=scenario.prompt,
                    max_steps=scenario.web_max_steps,
                    timeout_seconds=8,
                )
            )
        except WebWorkflowError as exc:
            return url, False, "tool_error", 1, "manual assisted"

        if scenario.id == "W3":
            passed = result.blocker_detected and not result.success
            failure_class = None if passed else "verification_error"
        elif scenario.id == "W8":
            passed = any("max_steps limit" in step for step in result.steps)
            failure_class = None if passed else "verification_error"
        else:
            passed = result.success and not result.blocker_detected
            failure_class = None if passed else "external_error"
        return url, passed, failure_class, 1, "full-auto"

    def _eval_stub_fetcher(self, url: str, timeout_seconds: int) -> tuple[int, str, str]:
        del timeout_seconds
        scenario_id = ""
        if "eval.stub/" in url:
            scenario_id = url.rstrip("/").rsplit("/", 1)[-1].upper()
        elif url.startswith("eval-stub://"):
            scenario_id = url.replace("eval-stub://", "", 1)
        else:
            for key in EVAL_STUB_PAGES:
                if key in url:
                    scenario_id = key
                    break
        if scenario_id not in EVAL_STUB_PAGES:
            return (200, "<html><title>Fallback</title></html>", url)
        return EVAL_STUB_PAGES[scenario_id]
