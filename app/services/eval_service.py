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
from app.services.code_retrieval_service import CodeRetrievalService
from app.services.eval_report_store import EvalReportStore
from app.services.eval_quality_judge_service import EvalQualityJudgeService
from app.services.mcp_registry_service import McpRegistryService
from app.services.search_provider import StubSearchProvider
from app.services.agent_tool_schema import TOOL_DEFINITIONS
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
_EVAL_HUMANEVAL_FIXTURE = "data/eval_fixtures/humaneval_add.py"
_EVAL_HUMANEVAL_BASELINE = "def add(a: int, b: int) -> int:\n    return a - b\n"


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
    tool_steps: tuple[dict[str, object], ...] = ()
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
    retrieval_query: str = ""
    retrieval_expect: str = ""
    platform_tool: str = ""
    cp_stack_id: str = ""
    cp_min_tasks: int = 5
    cp_expect_steps: tuple[str, ...] = ()
    schema_path: str = ""
    fixture_path: str = ""
    stub_check: str = ""
    expect_asset_mime: str = ""
    expect_min_dimension: int = 0
    max_cost_usd: float = 0.0
    enabled_tools: tuple[str, ...] = ()


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
        retrieval_service: Optional[CodeRetrievalService] = None,
        extra_scenarios_path: Optional[str] = None,
        extra_scenarios_paths: Optional[list[str]] = None,
        quality_judge: Optional[EvalQualityJudgeService] = None,
    ) -> None:
        self._scenarios = self._load_scenarios(scenarios_path)
        for extra_path in extra_scenarios_paths or []:
            if extra_path:
                path = Path(extra_path)
                if path.is_file():
                    self._scenarios = self._scenarios + self._load_scenarios(extra_path)
        if extra_scenarios_path:
            extra = Path(extra_scenarios_path)
            if extra.is_file():
                self._scenarios = self._scenarios + self._load_scenarios(extra_scenarios_path)
        self._task_service = task_service
        self._tooling = tooling_service
        self._browser = browser_service
        self._telemetry = telemetry
        self._report_store = report_store
        self._web_fetcher = web_fetcher
        self._retrieval = retrieval_service
        self._quality_judge = quality_judge

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
                    tool_steps=tuple(item.get("tool_steps") or []),
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
                    retrieval_query=str(item.get("retrieval_query", "")),
                    retrieval_expect=str(item.get("retrieval_expect", "")),
                    platform_tool=str(item.get("platform_tool", "")),
                    cp_stack_id=str(item.get("cp_stack_id", "")),
                    cp_min_tasks=int(item.get("cp_min_tasks", 5)),
                    cp_expect_steps=tuple(str(s) for s in (item.get("cp_expect_steps") or [])),
                    schema_path=str(item.get("schema_path", "")),
                    fixture_path=str(item.get("fixture_path", "")),
                    stub_check=str(item.get("stub_check", "")),
                    expect_asset_mime=str(item.get("expect_asset_mime", "")),
                    expect_min_dimension=int(item.get("expect_min_dimension", 0)),
                    max_cost_usd=float(item.get("max_cost_usd", 0)),
                    enabled_tools=tuple(str(t) for t in (item.get("enabled_tools") or [])),
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
        finally:
            if scenario.patch_path == _EVAL_PATCH_FIXTURE:
                self._reset_patch_fixture()

        duration_ms = int((time.perf_counter() - started) * 1000)
        result = {
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
            "response": message,
        }
        if self._quality_judge is not None:
            judgement = self._quality_judge.judge_scenario(
                prompt=scenario.prompt,
                response=message,
                category=scenario.category,
                status=status,
                task_success=result["task_success"],
            )
            result.update(judgement.as_dict())
        return result

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
        durations = sorted(int(item.get("duration_ms", 0)) for item in results)
        latency_p95_ms = self._percentile(durations, 95) if durations else 0
        estimated_cost_usd = round(
            sum(len(str(item.get("prompt", ""))) for item in results) * 0.000002,
            6,
        )

        report = {
            "run_id": run_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / len(results), 4) if results else 0.0,
            "latency_p95_ms": latency_p95_ms,
            "estimated_cost_usd": estimated_cost_usd,
            "category_filter": category,
            "results": results,
            "metrics": metrics.model_dump() if metrics else None,
        }
        quality_scores = [
            float(item["quality_score"])
            for item in results
            if item.get("quality_score") is not None
        ]
        judge_models = [
            str(item.get("judge_model", "")).strip().lower()
            for item in results
            if item.get("judge_model") is not None
        ]
        cloud_judge_hits = sum(1 for name in judge_models if name and name != "heuristic")
        cloud_judge_coverage = (
            round(cloud_judge_hits / len(judge_models), 4)
            if judge_models
            else 0.0
        )
        report["cloud_judge_coverage"] = cloud_judge_coverage
        if quality_scores and self._quality_judge is not None:
            report.update(self._quality_judge.summarize_scores(quality_scores))
        if persist_report and self._report_store is not None:
            self._report_store.append_suite_report(report)
        return report

    def list_reports(self, limit: int = 10) -> list[dict[str, object]]:
        if self._report_store is None:
            return []
        return self._report_store.list_recent(limit=limit)

    @staticmethod
    def pass_rate_by_category(results: list[dict[str, object]]) -> dict[str, float]:
        """Aggregate pass rate per eval scenario category from suite results."""
        totals: dict[str, list[bool]] = {}
        for item in results:
            category = str(item.get("category") or "unknown")
            passed = str(item.get("status", "")) == "passed"
            totals.setdefault(category, []).append(passed)
        return {
            category: round(sum(1 for ok in rows if ok) / len(rows), 4)
            for category, rows in sorted(totals.items())
            if rows
        }

    def build_dashboard(self, *, report_limit: int = 10) -> dict[str, object]:
        reports = self.list_reports(limit=report_limit)
        latest = reports[0] if reports else None
        metrics = self._telemetry.snapshot() if self._telemetry else None
        chat_p95_ms = None
        if metrics is not None:
            chat_p95_ms = getattr(metrics, "p95_latency_ms", None)
        suite_p95_ms = int(latest.get("latency_p95_ms", 0)) if latest else 0
        pass_rate = float(latest.get("pass_rate", 0.0)) if latest else 0.0
        cost_usd = float(latest.get("estimated_cost_usd", 0.0)) if latest else 0.0
        latest_results = list(latest.get("results") or []) if latest else []
        pass_by_category = self.pass_rate_by_category(latest_results)
        return {
            "pass_rate": pass_rate,
            "pass_rate_by_category": pass_by_category,
            "latency_p95_ms": suite_p95_ms or chat_p95_ms or 0,
            "chat_latency_p95_ms": chat_p95_ms,
            "estimated_cost_usd": cost_usd,
            "latest_run_id": str(latest.get("run_id", "")) if latest else None,
            "latest_total": int(latest.get("total", 0)) if latest else 0,
            "latest_passed": int(latest.get("passed", 0)) if latest else 0,
            "quality_median": float(latest.get("quality_median", 0.0)) if latest else 0.0,
            "quality_mean": float(latest.get("quality_mean", 0.0)) if latest else 0.0,
            "scenario_count": len(self._scenarios),
            "recent_reports": reports,
        }

    @staticmethod
    def _percentile(values: list[int], pct: int) -> int:
        if not values:
            return 0
        if len(values) == 1:
            return values[0]
        rank = max(0, min(len(values) - 1, int(round((pct / 100.0) * (len(values) - 1)))))
        return values[rank]

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
        if runner == "tool_sequence":
            return self._run_tool_sequence(scenario)
        if runner == "web":
            return self._run_web_scenario(scenario)
        if runner == "retrieval":
            return self._run_retrieval_scenario(scenario)
        if runner == "platform_web_search":
            return self._run_platform_web_search(scenario)
        if runner == "platform_mcp":
            return self._run_platform_mcp(scenario)
        if runner == "platform_spawn_tool":
            return self._run_platform_spawn_tool(scenario)
        if runner == "cross_platform_decompose":
            return self._run_cross_platform_decompose(scenario)
        if runner == "media_schema":
            return self._run_media_schema(scenario)
        if runner == "media_stub":
            return self._run_media_stub(scenario)
        if runner == "media_agent":
            return self._run_media_agent(scenario)
        raise ValueError(f"Unsupported runner: {runner}")

    def _run_cross_platform_decompose(
        self, scenario: EvalScenario
    ) -> tuple[str, bool, Optional[str], int, str]:
        from app.services.cross_platform_dev_service import CrossPlatformDevService

        goal = scenario.prompt.strip()
        service = CrossPlatformDevService()
        profile, platforms, tasks = service.decompose(
            goal,
            stack_id=scenario.cp_stack_id or None,
        )
        step_ids = {task.step_id for task in tasks}
        ok = len(tasks) >= max(1, scenario.cp_min_tasks)
        if scenario.cp_stack_id and profile.stack_id != scenario.cp_stack_id:
            ok = False
        for expected in scenario.cp_expect_steps:
            if expected not in step_ids:
                ok = False
        ref = f"stack={profile.stack_id} tasks={len(tasks)} platforms={[p.value for p in platforms]}"
        return ref, ok, None if ok else "cross_platform_plan", 1, "automated"

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
        elif scenario.patch_path == _EVAL_HUMANEVAL_FIXTURE:
            self._reset_humaneval_fixture()
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
            verify_result = self._tooling.execute_command(
                ExecuteCommandRequest(
                    command=scenario.verify_command,
                    path=scenario.tool_path or ".",
                    dry_run=False,
                    confirmed=True,
                )
            )
            if verify_result.executed and verify_result.exit_code == 0 and not scenario.expect_verify_failure:
                return (
                    f"{patch_result.path}|{verify_result.command}",
                    True,
                    None,
                    1,
                    "semi-auto",
                )
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

    def _run_tool_sequence(self, scenario: EvalScenario) -> tuple[str, bool, Optional[str], int, str]:
        if self._tooling is None:
            raise RuntimeError("Tooling service is not configured for eval runs.")
        if not scenario.tool_steps:
            raise ValueError("tool_sequence runner requires tool_steps.")
        refs: list[str] = []
        for index, step in enumerate(scenario.tool_steps):
            if not isinstance(step, dict):
                raise ValueError(f"tool_steps[{index}] must be an object.")
            op = str(step.get("op", "")).strip().lower()
            if op == "list":
                listing = self._tooling.list_files(
                    ListFilesRequest(
                        path=str(step.get("path", ".")),
                        pattern=str(step.get("pattern", "*")),
                    )
                )
                if not listing.files:
                    return f"step-{index}:list", False, "verification_error", 1, "semi-auto"
                refs.append(f"list:{len(listing.files)}")
            elif op == "read":
                content = self._tooling.read_file(
                    ReadFileRequest(path=str(step.get("path", ".")), max_bytes=8000)
                )
                if not content.content.strip():
                    return f"step-{index}:read", False, "verification_error", 1, "semi-auto"
                refs.append(f"read:{content.path}")
            elif op == "exec":
                command = str(step.get("command", "")).strip()
                if not command:
                    raise ValueError(f"tool_steps[{index}] exec requires command.")
                result = self._tooling.execute_command(
                    ExecuteCommandRequest(
                        command=command,
                        path=str(step.get("path", ".")),
                        dry_run=bool(step.get("dry_run", False)),
                        confirmed=bool(step.get("confirmed", False)),
                    )
                )
                blocked = result.risk_level.value == "blocked" and not result.executed
                dry_run = bool(step.get("dry_run", False))
                if blocked or (not result.executed and not dry_run):
                    return f"step-{index}:exec", False, "tool_error", 0 if blocked else 1, "semi-auto"
                refs.append(f"exec:{result.exit_code}")
            elif op == "patch":
                patch_path = str(step.get("patch_path", "")).strip()
                if not patch_path:
                    raise ValueError(f"tool_steps[{index}] patch requires patch_path.")
                if patch_path == _EVAL_PATCH_FIXTURE:
                    self._reset_patch_fixture()
                hunks = []
                patch_old = str(step.get("patch_old", ""))
                patch_new = str(step.get("patch_new", ""))
                if patch_old or patch_new:
                    hunks = [ApplyPatchHunk(old_text=patch_old, new_text=patch_new)]
                patch_result = self._tooling.apply_patch(
                    ApplyPatchRequest(
                        path=patch_path,
                        hunks=hunks,
                        create=bool(step.get("patch_create", False)),
                        dry_run=bool(step.get("patch_dry_run", True)),
                        confirmed=bool(step.get("patch_confirmed", False)),
                    )
                )
                blocked = patch_result.risk_level.value == "blocked"
                dry_run = bool(step.get("patch_dry_run", True))
                if blocked or (not patch_result.applied and not dry_run):
                    return f"step-{index}:patch", False, "safety_block" if blocked else "verification_error", 0 if blocked else 1, "semi-auto"
                refs.append(f"patch:{patch_result.path}")
            else:
                raise ValueError(f"Unsupported tool_sequence op: {op}")
        return " -> ".join(refs), True, None, 1, "semi-auto"

    def _reset_patch_fixture(self) -> None:
        if self._tooling is None:
            return
        target = self._tooling.root / _EVAL_PATCH_FIXTURE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_EVAL_PATCH_BASELINE, encoding="utf-8")

    def _reset_humaneval_fixture(self) -> None:
        if self._tooling is None:
            return
        target = self._tooling.root / _EVAL_HUMANEVAL_FIXTURE
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(_EVAL_HUMANEVAL_BASELINE, encoding="utf-8")

    def _run_web_scenario(self, scenario: EvalScenario) -> tuple[str, bool, Optional[str], int, str]:
        url = scenario.web_url
        fetcher = self._web_fetcher or self._eval_stub_fetcher
        browser = BrowserWorkflowService(fetcher=fetcher)
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

    def _run_retrieval_scenario(
        self, scenario: EvalScenario
    ) -> tuple[str, bool, Optional[str], int, str]:
        if self._retrieval is None:
            raise RuntimeError("Retrieval service is not configured for eval runs.")
        query = scenario.retrieval_query or scenario.prompt
        expect = scenario.retrieval_expect.strip()
        if not expect:
            raise ValueError("retrieval runner requires retrieval_expect.")
        hits = self._retrieval.search(query, limit=8)
        matched_paths = [hit.path for hit in hits if expect in hit.path.replace("\\", "/")]
        passed = len(matched_paths) > 0
        ref = matched_paths[0] if matched_paths else (hits[0].path if hits else query)
        return ref, passed, None if passed else "verification_error", 1, "semi-auto"

    def _run_platform_web_search(
        self, scenario: EvalScenario
    ) -> tuple[str, bool, Optional[str], int, str]:
        provider = StubSearchProvider()
        result = provider.search(scenario.prompt, max_results=3)
        passed = bool(result.citations) and len(result.hits) > 0
        return result.provider, passed, None if passed else "verification_error", 1, "semi-auto"

    def _run_platform_mcp(self, scenario: EvalScenario) -> tuple[str, bool, Optional[str], int, str]:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            registry = McpRegistryService(str(Path(tmp) / "mcp.json"))
            server = registry.upsert_server(
                name="eval",
                command="stub",
                allowed_tools=["ping"],
            )
            payload = registry.invoke_tool(server.server_id, "ping", {"probe": True})
        passed = "stub_ok" in payload
        return server.server_id, passed, None if passed else "verification_error", 1, "semi-auto"

    def _run_platform_spawn_tool(
        self, scenario: EvalScenario
    ) -> tuple[str, bool, Optional[str], int, str]:
        tool_name = scenario.platform_tool or "spawn_agent"
        passed = tool_name in TOOL_DEFINITIONS
        return tool_name, passed, None if passed else "verification_error", 1, "semi-auto"

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

    def _run_media_schema(
        self, scenario: EvalScenario
    ) -> tuple[str, bool, Optional[str], int, str]:
        from tests.test_media_studio_phase0 import _load_json, _validate_against_schema

        if not scenario.schema_path or not scenario.fixture_path:
            raise ValueError("media_schema requires schema_path and fixture_path.")
        schema = _load_json(Path(scenario.schema_path))
        fixture = _load_json(Path(scenario.fixture_path))
        if not isinstance(schema, dict):
            raise ValueError("Invalid schema JSON")
        errors = _validate_against_schema(fixture, schema)
        passed = len(errors) == 0
        ref = scenario.fixture_path
        return ref, passed, None if passed else "verification_error", 1, "automated"

    def _run_media_stub(
        self, scenario: EvalScenario
    ) -> tuple[str, bool, Optional[str], int, str]:
        passed = False
        ref = scenario.stub_check or "media_stub"
        if scenario.stub_check == "tools_v1_has_generate_image":
            raw = json.loads(Path("data/media/tools_v1.json").read_text(encoding="utf-8"))
            tools = raw.get("tools", [])
            names = {t.get("name") for t in tools if isinstance(t, dict)}
            passed = "generate_image" in names and "render_video" in names
        return ref, passed, None if passed else "verification_error", 1, "automated"

    def _run_media_agent(
        self, scenario: EvalScenario
    ) -> tuple[str, bool, Optional[str], int, str]:
        import tempfile

        from app.services.media_asset_store import MediaAssetStore
        from app.services.media_generation_service import MediaGenerationService

        tmp = tempfile.TemporaryDirectory()
        try:
            service = MediaGenerationService(
                asset_store=MediaAssetStore(tmp.name),
                enabled=True,
                image_provider_name="stub",
                ffmpeg_path="ffmpeg",
                ffprobe_path="ffprobe",
                jobs_db_path=str(Path(tmp.name) / "jobs.db"),
            )
            passed = True
            ref = scenario.id
            if "estimate_media_cost" in scenario.enabled_tools:
                est = service.estimate_cost(
                    storyboard_path="data/media/examples/storyboard.example.json"
                )
                passed = est.total_usd <= (scenario.max_cost_usd or 25.0)
                ref = f"cost={est.total_usd}"
            if "generate_image" in scenario.enabled_tools:
                img = service.generate_image(
                    prompt=scenario.prompt,
                    width=max(scenario.expect_min_dimension, 512),
                    height=max(scenario.expect_min_dimension, 512),
                    provider="stub",
                )
                passed = passed and img.asset.mime == (scenario.expect_asset_mime or "image/png")
                if scenario.expect_min_dimension:
                    passed = passed and img.asset.width >= scenario.expect_min_dimension
                ref = img.asset.asset_id
                if "vision_qa_media" in scenario.enabled_tools:
                    qa = service.vision_qa_media(asset_id=img.asset.asset_id, criteria=scenario.prompt)
                    passed = passed and qa.passed
            if "compose_media" in scenario.enabled_tools and "generate_image" not in scenario.enabled_tools:
                imgs = [
                    service.generate_image(prompt=f"slide {i}", width=320, height=240, provider="stub")
                    for i in range(3)
                ]
                composed = service.compose_media(
                    timeline={
                        "clips": [
                            {"asset_id": img.asset.asset_id, "duration_sec": 1.5} for img in imgs
                        ],
                        "preset": "youtube_16x9",
                    }
                )
                passed = composed.asset.mime == (scenario.expect_asset_mime or "video/mp4")
                ref = composed.asset.asset_id
            if "render_video" in scenario.enabled_tools:
                img = service.generate_image(prompt="hero", width=640, height=360, provider="stub")
                job = service.render_video(
                    prompt="motion",
                    source_asset_id=img.asset.asset_id,
                    duration_sec=3,
                    confirmed=True,
                )
                waited = service.wait_media_job(job_id=job.job_id)
                passed = passed and waited.status == "completed" and bool(waited.result_asset_id)
                ref = waited.result_asset_id or job.job_id
            if "export_lottie" in scenario.enabled_tools:
                imgs = [
                    service.generate_image(prompt=f"frame {i}", width=128, height=128, provider="stub")
                    for i in range(3)
                ]
                lottie = service.export_lottie(
                    asset_ids=[img.asset.asset_id for img in imgs],
                    fps=4,
                    width=128,
                )
                passed = passed and lottie.mime == (scenario.expect_asset_mime or "application/json")
                ref = lottie.asset_id
            return ref or scenario.id, passed, None if passed else "verification_error", 1, "semi-auto"
        finally:
            tmp.cleanup()
