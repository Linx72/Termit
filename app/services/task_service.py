from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Callable, Optional
from uuid import uuid4

from app.domain.schemas import (
    AgentProfileResponse,
    ListFilesRequest,
    ReadFileRequest,
    TaskCancelResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskEvent,
    TaskMode,
    TaskState,
    TaskStatusResponse,
    TaskType,
)
from app.services.agent_registry_store import AgentRegistryStore
from app.services.agent_templates_store import AgentTemplatesStore
from app.services.assignment_workspace_service import AssignmentWorkspaceService
from app.services.task_store import TaskStore
from app.services.telemetry_store import TelemetryStore
from app.services.task_agent_assignment import resolve_project_template_ids
from app.services.tooling_service import ToolingError, ToolingService
from app.services.training_signal_store import TrainingSignalStore


class TaskNotFoundError(Exception):
    pass


class TaskExecutionError(Exception):
    error_class = "external_error"


class PlanningError(TaskExecutionError):
    error_class = "planning_error"


class VerificationError(TaskExecutionError):
    error_class = "verification_error"


class ExternalError(TaskExecutionError):
    error_class = "external_error"


TaskAgentRunner = Callable[[str, TaskType, Optional[str], Optional[str]], str]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskService:
    """In-memory task lifecycle service for MVP iteration."""

    def __init__(
        self,
        tooling: ToolingService,
        store: TaskStore,
        max_attempts: int = 2,
        telemetry: TelemetryStore | None = None,
        training_signal_store: TrainingSignalStore | None = None,
        agent_runner: TaskAgentRunner | None = None,
        use_agent_for_auto: bool = False,
        task_agent_id: str = "",
        assignment_workspace: AssignmentWorkspaceService | None = None,
        agent_registry: AgentRegistryStore | None = None,
        agent_templates: AgentTemplatesStore | None = None,
    ) -> None:
        self._tooling = tooling
        self._store = store
        self._assignments = assignment_workspace
        self._max_attempts = max_attempts
        self._telemetry = telemetry
        self._training_signals = training_signal_store
        self._agent_runner = agent_runner
        self._use_agent_for_auto = use_agent_for_auto
        self._task_agent_id = task_agent_id.strip()
        self._agent_registry = agent_registry
        self._agent_templates = agent_templates
        self._lock = Lock()

    def create_task(self, payload: TaskCreateRequest) -> TaskCreateResponse:
        task_id = str(uuid4())
        now = _utc_now_iso()
        task = TaskStatusResponse(
            task_id=task_id,
            state=TaskState.queued,
            input=payload.input,
            task_type=payload.task_type,
            mode=payload.mode,
            session_id=payload.session_id,
            project_id=payload.project_id,
            created_at=now,
            updated_at=now,
            attempts=0,
            max_attempts=self._max_attempts,
            events=[
                TaskEvent(
                    event_type="task_received",
                    state=TaskState.queued,
                    message="Task accepted and queued for execution",
                    timestamp=now,
                )
            ],
        )

        with self._lock:
            self._store.put_task(task)

        # MVP synchronous execution to validate lifecycle contract.
        self._run_task(task_id)
        created = self.get_task(task_id)
        return TaskCreateResponse(
            task_id=created.task_id,
            state=created.state,
            created_at=created.created_at,
        )

    def list_tasks(self, limit: int = 50) -> list[TaskStatusResponse]:
        return self._store.list_tasks(limit=limit)

    def get_task(self, task_id: str) -> TaskStatusResponse:
        task = self._store.get_task(task_id)
        if task is None:
            raise TaskNotFoundError(f"Task not found: {task_id}")
        return TaskStatusResponse.model_validate(task.model_dump())

    def get_task_events(self, task_id: str) -> list[TaskEvent]:
        task = self.get_task(task_id)
        return task.events

    def cancel_task(self, task_id: str) -> TaskCancelResponse:
        with self._lock:
            task = self._store.get_task(task_id)
            if task is None:
                raise TaskNotFoundError(f"Task not found: {task_id}")
            if task.state in {TaskState.completed, TaskState.failed, TaskState.cancelled}:
                return TaskCancelResponse(
                    task_id=task_id,
                    cancelled=False,
                    state=task.state,
                )

            now = _utc_now_iso()
            task.state = TaskState.cancelled
            task.updated_at = now
            task.events.append(
                TaskEvent(
                    event_type="task_cancelled",
                    state=TaskState.cancelled,
                    message="Task cancelled by user request",
                    timestamp=now,
                )
            )
            self._store.put_task(task)
            return TaskCancelResponse(
                task_id=task_id,
                cancelled=True,
                state=task.state,
            )

    def _run_task(self, task_id: str) -> None:
        with self._lock:
            task = self._store.get_task(task_id)
            if task is None:
                return
            self._set_state_locked(
                task,
                TaskState.running,
                "execution_started",
                "Planning and execution started",
            )
            self._store.put_task(task)

        task = self.get_task(task_id)
        if task.mode == TaskMode.guided:
            with self._lock:
                current = self._store.get_task(task_id)
                if current is None:
                    return
                current.report = "Task is in guided mode and waiting for manual step-by-step execution."
                self._append_event_locked(
                    current,
                    "guided_wait",
                    TaskState.running,
                    "Guided mode paused after planning",
                )
                self._store.put_task(current)
            return

        if self._use_agent_for_auto and self._agent_runner is not None:
            try:
                self._ensure_project_agents(task)
                if self._is_cross_platform_task(task_id):
                    self._run_cross_platform_via_agent(task_id)
                else:
                    self._run_via_agent(task_id)
                self._record_task_telemetry(completed=True, auto_mode=True, failure_class=None)
            except TaskExecutionError as exc:
                self._fail(task_id, exc.error_class, str(exc))
                self._record_task_telemetry(
                    completed=False,
                    auto_mode=True,
                    failure_class=exc.error_class,
                )
            except Exception as exc:  # noqa: BLE001
                self._fail(task_id, "external_error", f"Unexpected task failure: {exc}")
                self._record_task_telemetry(
                    completed=False,
                    auto_mode=True,
                    failure_class="external_error",
                )
            return

        try:
            steps = self._build_plan(task)
            self._append_event(task_id, "plan_ready", TaskState.running, f"Execution plan prepared ({len(steps)} steps)")

            execution_notes: list[str] = []
            for step in steps:
                note = self._execute_with_retry(task_id, step)
                execution_notes.append(note)

            self._set_state(task_id, TaskState.verifying, "verification_started", "Verifying task output")
            self._verify(task_id, execution_notes)
            self._complete(task_id, execution_notes)
            self._record_task_telemetry(completed=True, auto_mode=True, failure_class=None)
        except TaskExecutionError as exc:
            self._fail(task_id, exc.error_class, str(exc))
            self._record_task_telemetry(
                completed=False,
                auto_mode=True,
                failure_class=exc.error_class,
            )
        except Exception as exc:  # noqa: BLE001
            self._fail(task_id, "external_error", f"Unexpected task failure: {exc}")
            self._record_task_telemetry(
                completed=False,
                auto_mode=True,
                failure_class="external_error",
            )

    def _build_plan(self, task: TaskStatusResponse) -> list[str]:
        from app.services.cross_platform_dev_service import CrossPlatformDevService

        text = task.input.lower()
        if "[fail-plan]" in text:
            raise PlanningError("Planner failed due to malformed task constraints.")

        if CrossPlatformDevService.is_cross_platform_task(task.input):
            return CrossPlatformDevService().plan_orchestration_steps(task.input, task.task_type)

        steps = ["analyze_input"]
        if task.task_type == TaskType.online_project:
            steps.extend(["scaffold_assignment", "inspect_deliverables"])
        elif task.task_type == TaskType.online_research:
            steps.append("online_research_brief")
        elif task.task_type in {TaskType.coding, TaskType.review, TaskType.debug, TaskType.explain}:
            steps.append("inspect_workspace")
        if "readme" in text:
            steps.append("read_readme")
        steps.append("compose_report")
        return steps

    def _execute_with_retry(self, task_id: str, step: str) -> str:
        last_error: TaskExecutionError | None = None
        for attempt in range(1, self._max_attempts + 1):
            self._set_attempts(task_id, attempt)
            self._append_event(
                task_id,
                "step_started",
                TaskState.running,
                f"Step '{step}' started (attempt {attempt}/{self._max_attempts})",
            )
            try:
                note = self._execute_step(task_id, step, attempt)
                self._append_event(
                    task_id,
                    "step_completed",
                    TaskState.running,
                    f"Step '{step}' completed",
                )
                return note
            except TaskExecutionError as exc:
                last_error = exc
                self._append_event(
                    task_id,
                    "step_failed",
                    TaskState.running,
                    f"Step '{step}' failed ({exc.error_class}): {exc}",
                )
                if attempt >= self._max_attempts:
                    break
                self._append_event(
                    task_id,
                    "retry_scheduled",
                    TaskState.running,
                    f"Retrying step '{step}' after failure",
                )

        assert last_error is not None
        raise last_error

    def _execute_step(self, task_id: str, step: str, attempt: int) -> str:
        task = self.get_task(task_id)
        text = task.input.lower()

        if step == "analyze_input":
            if len(task.input.strip()) < 3:
                raise PlanningError("Task input is too short to execute.")
            return "Intent analyzed."

        if step == "analyze_requirements":
            return "Requirements analyzed for cross-platform delivery."

        if step == "detect_stack_and_targets":
            from app.services.cross_platform_dev_service import CrossPlatformDevService

            service = CrossPlatformDevService()
            profile, platforms, tasks = service.decompose(task.input)
            return (
                f"Stack {profile.name} ({profile.stack_id}) for "
                f"{', '.join(p.value for p in platforms)} — {len(tasks)} atomic steps."
            )

        if step.startswith("atomic_"):
            from app.services.cross_platform_dev_service import CrossPlatformDevService

            service = CrossPlatformDevService()
            _, _, tasks = service.decompose(task.input)
            slug = step.removeprefix("atomic_")
            matched = next((item for item in tasks if item.step_id.replace("-", "_") == slug), None)
            if matched is None:
                matched = next(
                    (item for item in tasks if slug in item.step_id.replace("-", "_")),
                    None,
                )
            title = matched.title if matched else slug.replace("_", " ")
            verify = matched.verify_hint if matched else "Step verify pending"
            return f"Atomic step '{title}' planned. Verify: {verify}"

        if step == "compose_delivery":
            if "[fail-tool]" in text:
                raise ExternalError("External provider timeout while composing report.")
            if "[retry-demo]" in text and attempt == 1:
                raise ExternalError("Transient external error detected (simulated).")
            return "Cross-platform delivery report drafted."

        if step == "validate_tests":
            return "Test validation step recorded for cross-platform task."

        if step == "inspect_workspace":
            try:
                listing = self._tooling.list_files(ListFilesRequest(path="app", pattern="*.py"))
                return f"Workspace inspected: found {len(listing.files)} Python files in app/."
            except ToolingError:
                listing = self._tooling.list_files(ListFilesRequest(path=".", pattern="*.py"))
                return f"Workspace inspected: found {len(listing.files)} Python files in project root."

        if step == "read_readme":
            try:
                content = self._tooling.read_file(ReadFileRequest(path="README.md", max_bytes=3000))
                return f"README analyzed ({len(content.content)} chars)."
            except ToolingError as exc:
                raise VerificationError(f"Could not read README for requested analysis: {exc}") from exc

        if step == "scaffold_assignment":
            if self._assignments is None:
                return "Assignment workspace service not configured."
            from app.domain.schemas import AssignmentCreateRequest

            title = task.input.strip().splitlines()[0][:120] or "Online project"
            created = self._assignments.create(
                AssignmentCreateRequest(
                    title=title,
                    brief=task.input,
                    success_criteria=["Deliverables in deliverables/", "Journal updated"],
                )
            )
            return f"Assignment workspace created: {created.assignment_id} at {created.root_path}"

        if step == "inspect_deliverables":
            if self._assignments is None:
                return "No assignment workspace configured."
            from pathlib import Path

            recent = self._assignments.list_assignments(limit=1)
            if not recent:
                return "No assignment folders found."
            deliverables = Path(recent[0].deliverables_path)
            count = sum(1 for item in deliverables.iterdir() if item.is_file())
            return f"Deliverables folder has {count} file(s) at {deliverables}."

        if step == "online_research_brief":
            return (
                "Online research brief prepared. Use agent with web_search + web_automation "
                "or POST /api/automation/web for live URLs."
            )

        if step == "compose_report":
            if "[fail-tool]" in text:
                raise ExternalError("External provider timeout while composing report.")
            if "[retry-demo]" in text and attempt == 1:
                raise ExternalError("Transient external error detected (simulated).")
            return "Execution report drafted."

        raise PlanningError(f"Unknown plan step: {step}")

    def _is_cross_platform_task(self, task_id: str) -> bool:
        from app.services.cross_platform_dev_service import CrossPlatformDevService

        task = self.get_task(task_id)
        return CrossPlatformDevService.is_cross_platform_task(task.input)

    def _run_cross_platform_via_agent(self, task_id: str) -> None:
        from app.services.cross_platform_dev_service import CrossPlatformDevService

        task = self.get_task(task_id)
        service = CrossPlatformDevService()
        profile, platforms, tasks = service.decompose(task.input)
        if not tasks:
            raise PlanningError("Cross-platform decomposition produced no steps.")

        self._append_event(
            task_id,
            "cross_platform_plan",
            TaskState.running,
            (
                f"Atomic workflow: {profile.stack_id} · "
                f"{len(tasks)} steps · template {profile.agent_template_id}"
            ),
        )

        execution_notes: list[str] = []
        session_id = task.session_id
        for index, atomic in enumerate(tasks):
            prompt = service.format_atomic_prompt(
                task.input,
                profile,
                platforms,
                atomic,
                index=index,
                total=len(tasks),
            )
            self._append_event(
                task_id,
                "atomic_step_started",
                TaskState.running,
                f"Atomic step {index + 1}/{len(tasks)}: {atomic.title}",
            )
            if self._agent_runner is None:
                raise PlanningError("Agent runner is not configured.")
            response = self._agent_runner(prompt, task.task_type, session_id, task.project_id)
            execution_notes.append(f"[{atomic.step_id}] {response[:500]}")
            self._append_event(
                task_id,
                "atomic_step_completed",
                TaskState.running,
                f"Atomic step {index + 1}/{len(tasks)} completed",
            )

        self._set_state(task_id, TaskState.verifying, "verification_started", "Verifying agent output")
        self._verify(task_id, execution_notes)
        self._complete(task_id, execution_notes)

    def _run_via_agent(self, task_id: str) -> None:
        task = self.get_task(task_id)
        self._append_event(
            task_id,
            "agent_dispatch",
            TaskState.running,
            f"Dispatching to agent for task_type={task.task_type.value}",
        )
        if self._agent_runner is None:
            raise PlanningError("Agent runner is not configured.")
        response = self._agent_runner(task.input, task.task_type, task.session_id, task.project_id)
        execution_notes = [response]
        self._append_event(
            task_id,
            "agent_completed",
            TaskState.running,
            f"Agent completed ({len(response)} chars)",
        )
        self._set_state(task_id, TaskState.verifying, "verification_started", "Verifying agent output")
        self._verify(task_id, execution_notes)
        self._complete(task_id, execution_notes)

    def _ensure_project_agents(self, task: TaskStatusResponse) -> None:
        # For project-scoped tasks we proactively ensure required helper agents
        # (coding/research/media/security etc.) exist before dispatching the run.
        project_id = (task.project_id or "").strip()
        if not project_id:
            return
        if self._agent_registry is None or self._agent_templates is None:
            return

        template_ids = self._select_project_template_ids(task.task_type, task.input)
        attached: list[str] = []
        for template_id in template_ids:
            template = self._agent_templates.get_template(template_id)
            if template is None:
                continue
            request = self._agent_templates.to_create_request(template_id)
            existing = self._find_agent_by_template_name(request.name, request.task_type)
            agent = existing or self._agent_registry.create_agent(request)
            attached.append(f"{template_id}:{agent.agent_id}")

        if attached:
            self._append_event(
                task.task_id,
                "project_agents_attached",
                TaskState.running,
                f"Project {project_id}: attached agents {', '.join(attached)}",
            )

    def _find_agent_by_template_name(
        self,
        name: str,
        task_type: TaskType,
    ) -> AgentProfileResponse | None:
        if self._agent_registry is None:
            return None
        for agent in self._agent_registry.list_agents():
            if agent.name == name and agent.task_type == task_type:
                return agent
        return None

    @staticmethod
    def _select_project_template_ids(task_type: TaskType, instruction: str) -> list[str]:
        return resolve_project_template_ids(task_type, instruction)

    def _verify(self, task_id: str, execution_notes: list[str]) -> None:
        task = self.get_task(task_id)
        if not execution_notes:
            raise VerificationError("Verification failed: execution produced no notes.")
        if "[fail-verify]" in task.input.lower():
            raise VerificationError("Verification assertions failed for this task.")

        self._append_event(
            task_id,
            "verification_passed",
            TaskState.verifying,
            "Verification checks passed",
        )

    def _complete(self, task_id: str, execution_notes: list[str]) -> None:
        with self._lock:
            task = self._store.get_task(task_id)
            if task is None:
                return
            task.failure_class = None
            task.error = None
            task.report = self._build_report(task, execution_notes)
            self._set_state_locked(
                task,
                TaskState.completed,
                "task_completed",
                "Task completed successfully",
            )
            self._store.put_task(task)
            if self._training_signals is not None:
                trajectory = "\n".join(
                    f"[{event.event_type}] {event.message}"
                    for event in task.events
                    if event.message.strip()
                )
                self._training_signals.try_capture_task(
                    task_id=task.task_id,
                    instruction=task.input,
                    report=task.report or "",
                    task_type=task.task_type.value,
                    session_id=task.session_id,
                    trajectory=trajectory,
                )

    def _fail(self, task_id: str, failure_class: str, reason: str) -> None:
        with self._lock:
            task = self._store.get_task(task_id)
            if task is None:
                return
            task.failure_class = failure_class
            task.error = reason
            task.report = (
                "Task execution failed.\n"
                f"- Failure class: {failure_class}\n"
                f"- Reason: {reason}\n"
                "- Next step: inspect events and retry with refined input or constraints."
            )
            self._set_state_locked(task, TaskState.failed, "task_failed", reason)
            self._store.put_task(task)

    def _build_report(self, task: TaskStatusResponse, notes: list[str]) -> str:
        return (
            "Task execution completed.\n"
            f"- Task type: {task.task_type.value}\n"
            f"- Mode: {task.mode.value}\n"
            f"- Attempts used: {task.attempts}/{task.max_attempts}\n"
            f"- Steps completed: {len(notes)}\n"
            "- Notes: " + "; ".join(notes)
        )

    def _set_state(
        self,
        task_id: str,
        state: TaskState,
        event_type: str,
        message: str,
    ) -> None:
        with self._lock:
            task = self._store.get_task(task_id)
            if task is None:
                return
            self._set_state_locked(task, state, event_type, message)
            self._store.put_task(task)

    def _append_event(
        self,
        task_id: str,
        event_type: str,
        state: TaskState,
        message: str,
    ) -> None:
        with self._lock:
            task = self._store.get_task(task_id)
            if task is None:
                return
            self._append_event_locked(task, event_type, state, message)
            self._store.put_task(task)

    def _set_attempts(self, task_id: str, attempts: int) -> None:
        with self._lock:
            task = self._store.get_task(task_id)
            if task is None:
                return
            task.attempts = attempts
            task.updated_at = _utc_now_iso()
            self._store.put_task(task)

    def _set_state_locked(
        self,
        task: TaskStatusResponse,
        state: TaskState,
        event_type: str,
        message: str,
    ) -> None:
        task.state = state
        task.updated_at = _utc_now_iso()
        self._append_event_locked(task, event_type, state, message)

    def _append_event_locked(
        self,
        task: TaskStatusResponse,
        event_type: str,
        state: TaskState,
        message: str,
    ) -> None:
        task.events.append(
            TaskEvent(
                event_type=event_type,
                state=state,
                message=message,
                timestamp=task.updated_at,
            )
        )

    def _record_task_telemetry(
        self,
        *,
        completed: bool,
        auto_mode: bool,
        failure_class: str | None,
    ) -> None:
        if self._telemetry is None:
            return
        self._telemetry.record_task(
            completed=completed,
            auto_mode=auto_mode,
            failure_class=failure_class,
        )
