from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.domain.schemas import (
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
from app.services.task_store import TaskStore
from app.services.telemetry_store import TelemetryStore
from app.services.tooling_service import ToolingError, ToolingService


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
    ) -> None:
        self._tooling = tooling
        self._store = store
        self._max_attempts = max_attempts
        self._telemetry = telemetry
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
        text = task.input.lower()
        if "[fail-plan]" in text:
            raise PlanningError("Planner failed due to malformed task constraints.")

        steps = ["analyze_input"]
        if task.task_type in {TaskType.coding, TaskType.review, TaskType.debug, TaskType.explain}:
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

        if step == "compose_report":
            if "[fail-tool]" in text:
                raise ExternalError("External provider timeout while composing report.")
            if "[retry-demo]" in text and attempt == 1:
                raise ExternalError("Transient external error detected (simulated).")
            return "Execution report drafted."

        raise PlanningError(f"Unknown plan step: {step}")

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
