from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from queue import Empty, Full
from threading import Event, Lock, Thread
import time
from typing import Optional
from uuid import uuid4

from app.domain.schemas import (
    AgentProfileCreateRequest,
    AgentProfileResponse,
    AgentRunCancelResponse,
    AgentRunCreateResponse,
    AgentRunEvent,
    AgentRunListResponse,
    AgentRunRecordResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentRunState,
    ApplyPatchRequest,
    ApplyPatchResponse,
    ChatMessage,
    ChatRequest,
    ExecuteCommandRequest,
    ExecuteCommandResponse,
    ListFilesRequest,
    ListFilesResponse,
    ReadFileRequest,
    ReadFileResponse,
    WebAutomationRequest,
    WebAutomationResponse,
)
from app.services.agent_registry_store import AgentRegistryStore
from app.services.agent_run_store import AgentRunStore
from app.services.agent_run_queue import AgentRunQueue
from app.services.agent_loop_service import AgentLoopError, AgentLoopService, build_tool_arguments
from app.services.agent_memory_store import AgentMemoryStore
from app.services.browser_workflow_service import BrowserWorkflowService
from app.services.chat_service import ChatService
from app.services.tooling_service import ToolingService
from app.services.training_signal_store import TrainingSignalStore


class AgentNotFoundError(Exception):
    pass


class AgentRunNotFoundError(Exception):
    pass


class AgentQueueFullError(Exception):
    pass


class AgentPermissionError(Exception):
    pass


class AgentOnlineError(Exception):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentService:
    def __init__(
        self,
        chat_service: ChatService,
        registry: AgentRegistryStore,
        run_store: AgentRunStore,
        tooling: ToolingService,
        browser_workflow: BrowserWorkflowService,
        agent_memory_store: Optional[AgentMemoryStore] = None,
        agent_loop_service: Optional[AgentLoopService] = None,
        max_concurrency: int = 2,
        max_queue_size: int = 100,
        run_max_attempts: int = 2,
        run_retry_backoff_ms: int = 250,
        max_events_per_run: int = 500,
        max_response_chars: int = 12000,
        retention_days: int = 14,
        training_signal_store: Optional[TrainingSignalStore] = None,
        verify_after_patch: bool = False,
        verify_cmd: str = "",
    ) -> None:
        self._chat_service = chat_service
        self._registry = registry
        self._run_store = run_store
        self._tooling = tooling
        self._browser_workflow = browser_workflow
        self._agent_memory = agent_memory_store
        self._loop_service = agent_loop_service or AgentLoopService()
        self._run_queue: AgentRunQueue[tuple[str, str, AgentRunRequest]] = AgentRunQueue(
            maxsize=max(1, max_queue_size)
        )
        self._run_max_attempts = max(1, run_max_attempts)
        self._run_retry_backoff_ms = max(0, run_retry_backoff_ms)
        self._max_events_per_run = max(1, max_events_per_run)
        self._max_response_chars = max(256, max_response_chars)
        self._retention_days = max(1, retention_days)
        self._training_signals = training_signal_store
        self._verify_after_patch = verify_after_patch
        self._verify_cmd = verify_cmd.strip()
        self._queue_capacity = max(1, max_queue_size)
        self._worker_count = max(1, max_concurrency)
        self._lock = Lock()
        self._workers: list[Thread] = []
        self._stop = Event()
        self.start()

    def start(self) -> None:
        if self._stop.is_set():
            self._stop.clear()
        with self._lock:
            alive = [worker for worker in self._workers if worker.is_alive()]
            self._workers = alive
            missing = max(0, self._worker_count - len(self._workers))
            next_index = len(self._workers)
            for offset in range(missing):
                worker = Thread(
                    target=self._worker_loop,
                    name=f"agent-runner-{next_index + offset}",
                    daemon=True,
                )
                worker.start()
                self._workers.append(worker)

    def stop(self) -> None:
        self._stop.set()
        for worker in list(self._workers):
            worker.join(timeout=2)
        self._workers = []

    def create_agent(self, payload: AgentProfileCreateRequest) -> AgentProfileResponse:
        return self._registry.create_agent(payload)

    def list_agents(self) -> list[AgentProfileResponse]:
        return self._registry.list_agents()

    def get_agent(self, agent_id: str) -> AgentProfileResponse:
        profile = self._registry.get_agent(agent_id)
        if profile is None:
            raise AgentNotFoundError(f"Agent not found: {agent_id}")
        return profile

    def create_run(self, agent_id: str, payload: AgentRunRequest) -> AgentRunCreateResponse:
        profile = self.get_agent(agent_id)
        run_id = f"arun_{uuid4().hex[:12]}"
        now = _utc_now_iso()
        queued_position = self._run_queue.qsize() + 1
        record = AgentRunRecordResponse(
            run_id=run_id,
            agent_id=agent_id,
            agent_name=profile.name,
            state=AgentRunState.queued,
            created_at=now,
            updated_at=now,
            input=payload.input,
            session_id=payload.session_id,
            attempts=0,
            max_attempts=self._run_max_attempts,
        )
        with self._lock:
            self._run_store.put_run(record)
            self._append_event(
                run_id=run_id,
                event_type="run_queued",
                state=AgentRunState.queued,
                message="Agent run accepted and queued.",
                attempt=0,
            )

        try:
            self._run_queue.put_nowait((run_id, agent_id, payload), priority=payload.priority)
        except Full as exc:
            with self._lock:
                failed_record = record.model_copy(deep=True)
                failed_record.state = AgentRunState.failed
                failed_record.updated_at = _utc_now_iso()
                failed_record.error = "Queue is full."
                self._run_store.put_run(failed_record)
                self._append_event(
                    run_id=run_id,
                    event_type="run_queue_rejected",
                    state=AgentRunState.failed,
                    message="Run rejected because queue is full.",
                    attempt=0,
                )
            raise AgentQueueFullError("Agent execution queue is full.") from exc

        return AgentRunCreateResponse(
            run_id=run_id,
            state=AgentRunState.queued,
            queued_position=queued_position,
        )

    def get_run(self, run_id: str) -> AgentRunRecordResponse:
        with self._lock:
            record = self._run_store.get_run(run_id)
        if record is None:
            raise AgentRunNotFoundError(f"Agent run not found: {run_id}")
        return record

    def list_runs(self, agent_id: str | None = None, limit: int = 50) -> AgentRunListResponse:
        safe_limit = max(1, min(limit, 200))
        with self._lock:
            if agent_id:
                selected = self._run_store.list_runs_by_agent(agent_id=agent_id, limit=safe_limit)
            else:
                selected = self._run_store.list_runs(limit=safe_limit)
        return AgentRunListResponse(runs=selected, total=len(selected))

    def list_dlq_runs(self, limit: int = 50) -> AgentRunListResponse:
        safe_limit = max(1, min(limit, 200))
        with self._lock:
            all_runs = self._run_store.list_runs(limit=1000)
        failed = [run for run in all_runs if run.state == AgentRunState.failed]
        failed.sort(key=lambda item: item.updated_at, reverse=True)
        selected = failed[:safe_limit]
        return AgentRunListResponse(runs=selected, total=len(selected))

    def replay_run(self, run_id: str) -> AgentRunCreateResponse:
        run = self.get_run(run_id)
        if run.state != AgentRunState.failed:
            raise ValueError(f"Run {run_id} is not in failed/dead-letter state.")
        payload = AgentRunRequest(input=run.input, session_id=run.session_id)
        return self.create_run(run.agent_id, payload)

    def replay_dlq(self, limit: int = 5) -> list[AgentRunCreateResponse]:
        safe_limit = max(1, min(limit, 20))
        dlq = self.list_dlq_runs(limit=safe_limit)
        replayed: list[AgentRunCreateResponse] = []
        for run in dlq.runs:
            replayed.append(self.replay_run(run.run_id))
        return replayed

    def get_run_events(self, run_id: str, limit: int = 500) -> list[AgentRunEvent]:
        with self._lock:
            record = self._run_store.get_run(run_id)
            if record is None:
                raise AgentRunNotFoundError(f"Agent run not found: {run_id}")
            return self._run_store.get_events(run_id=run_id, limit=limit)

    def queue_metrics(self) -> dict[str, object]:
        with self._lock:
            by_state = self._run_store.count_runs_by_state()
            total_runs = self._run_store.count_runs()
            queue_size = self._run_queue.qsize()
            alive_workers = sum(1 for worker in self._workers if worker.is_alive())
        active_runs = int(by_state.get(AgentRunState.running.value, 0))
        utilization = round((queue_size / self._queue_capacity) * 100, 2)
        return {
            "queue_size": queue_size,
            "queue_capacity": self._queue_capacity,
            "queue_utilization_percent": utilization,
            "worker_count": self._worker_count,
            "alive_workers": alive_workers,
            "total_runs": total_runs,
            "by_state": by_state,
            "active_runs": active_runs,
        }

    def cleanup_runs(self, retention_days: int | None = None, dry_run: bool = False) -> dict[str, object]:
        safe_days = max(1, retention_days if retention_days is not None else self._retention_days)
        cutoff_seconds = time.time() - (safe_days * 24 * 60 * 60)
        cutoff = datetime.fromtimestamp(cutoff_seconds, tz=timezone.utc).isoformat()
        with self._lock:
            deleted_runs, deleted_events = self._run_store.cleanup_old_runs(
                cutoff_iso=cutoff,
                terminal_states={AgentRunState.completed, AgentRunState.failed, AgentRunState.cancelled},
                dry_run=dry_run,
            )
            remaining = self._run_store.count_runs()
        return {
            "dry_run": dry_run,
            "retention_days": safe_days,
            "cutoff_timestamp": cutoff,
            "deleted_runs": deleted_runs,
            "deleted_events": deleted_events,
            "remaining_runs": remaining,
        }

    def cancel_run(self, run_id: str) -> AgentRunCancelResponse:
        with self._lock:
            record = self._run_store.get_run(run_id)
            if record is None:
                raise AgentRunNotFoundError(f"Agent run not found: {run_id}")
            if record.state == AgentRunState.queued:
                record.state = AgentRunState.cancelled
                record.updated_at = _utc_now_iso()
                self._run_store.put_run(record)
                self._append_event(
                    run_id=run_id,
                    event_type="run_cancelled",
                    state=AgentRunState.cancelled,
                    message="Run cancelled before execution.",
                    attempt=record.attempts,
                )
                return AgentRunCancelResponse(run_id=run_id, cancelled=True, state=record.state)
            return AgentRunCancelResponse(run_id=run_id, cancelled=False, state=record.state)

    def list_agent_memory(self, agent_id: str, limit: int = 20) -> list[dict[str, str]]:
        self.get_agent(agent_id)
        if self._agent_memory is None:
            return []
        return self._agent_memory.list_entries(agent_id, limit=limit)

    async def run_agent(self, agent_id: str, payload: AgentRunRequest) -> AgentRunResponse:
        profile = self.get_agent(agent_id)
        return await self._run_with_profile(profile, payload)

    def list_files_as_agent(self, agent_id: str, payload: ListFilesRequest) -> ListFilesResponse:
        self._ensure_tool_allowed(agent_id, "list_files")
        return self._tooling.list_files(payload)

    def read_file_as_agent(self, agent_id: str, payload: ReadFileRequest) -> ReadFileResponse:
        self._ensure_tool_allowed(agent_id, "read_file")
        return self._tooling.read_file(payload)

    def execute_command_as_agent(
        self,
        agent_id: str,
        payload: ExecuteCommandRequest,
    ) -> ExecuteCommandResponse:
        self._ensure_tool_allowed(agent_id, "execute_command")
        return self._tooling.execute_command(payload)

    def apply_patch_as_agent(
        self,
        agent_id: str,
        payload: ApplyPatchRequest,
    ) -> ApplyPatchResponse:
        self._ensure_tool_allowed(agent_id, "apply_patch")
        return self._tooling.apply_patch(payload)

    def run_online_as_agent(self, agent_id: str, payload: WebAutomationRequest) -> WebAutomationResponse:
        self._ensure_tool_allowed(agent_id, "web_automation")
        profile = self.get_agent(agent_id)
        if not profile.allow_online:
            raise AgentOnlineError(f"Agent '{profile.name}' is not configured for online execution.")
        return self._browser_workflow.run(payload)

    async def _run_with_profile(
        self,
        profile: AgentProfileResponse,
        payload: AgentRunRequest,
        *,
        run_id: str | None = None,
        attempt: int = 1,
    ) -> AgentRunResponse:
        if payload.online_url:
            return self._run_online_request(profile, payload)

        use_loop = (
            profile.use_tool_loop
            if payload.use_tool_loop is None
            else payload.use_tool_loop
        )
        if use_loop:
            return await self._run_with_tool_loop(
                profile,
                payload,
                run_id=run_id,
                attempt=attempt,
            )

        chat_request = ChatRequest(
            message=payload.input,
            task_type=profile.task_type,
            model=profile.model,
            session_id=payload.session_id,
            use_memory=profile.use_memory if payload.use_memory is None else payload.use_memory,
            use_retrieval=profile.use_retrieval if payload.use_retrieval is None else payload.use_retrieval,
            retrieval_limit=payload.retrieval_limit
            if payload.retrieval_limit is not None
            else profile.retrieval_limit,
            retrieval_path_prefix=payload.retrieval_path_prefix
            if payload.retrieval_path_prefix is not None
            else profile.retrieval_path_prefix,
            temperature=payload.temperature if payload.temperature is not None else profile.temperature,
            max_tokens=payload.max_tokens if payload.max_tokens is not None else profile.max_tokens,
            history=[ChatMessage(role="system", content=profile.system_prompt)],
        )
        result = await self._chat_service.chat(chat_request)
        return AgentRunResponse(
            agent_id=profile.agent_id,
            agent_name=profile.name,
            provider=result.provider,
            model=result.model,
            task_type=result.task_type,
            session_id=result.session_id,
            attempted_models=result.attempted_models,
            response=result.response,
        )

    async def _run_with_tool_loop(
        self,
        profile: AgentProfileResponse,
        payload: AgentRunRequest,
        *,
        run_id: str | None = None,
        attempt: int = 1,
    ) -> AgentRunResponse:
        memory_context: list[str] = []
        if profile.use_long_term_memory and self._agent_memory is not None:
            memory_context = self._agent_memory.get_context(profile.agent_id)

        def tool_fn(tool_name: str, arguments: dict[str, object]) -> str:
            observation, side_effects = self._invoke_loop_tool(
                profile.agent_id,
                profile,
                tool_name,
                arguments,
            )
            for event_type, message in side_effects:
                if run_id:
                    self._append_event(
                        run_id=run_id,
                        event_type=event_type,
                        state=AgentRunState.running,
                        message=message,
                        attempt=attempt,
                    )
            return observation

        def on_step(step) -> None:  # type: ignore[no-untyped-def]
            if not run_id:
                return
            message = f"Step {step.step}: {step.action}"
            if step.tool:
                message += f" ({step.tool})"
            self._append_event(
                run_id=run_id,
                event_type="tool_loop_step",
                state=AgentRunState.running,
                message=message,
                attempt=attempt,
            )

        loop_result = await self._loop_service.run(
            profile=profile,
            payload=payload,
            chat_fn=self._chat_service.chat,
            tool_fn=tool_fn,
            memory_context=memory_context,
            max_steps=profile.max_tool_steps,
            on_step=on_step,
        )
        return AgentRunResponse(
            agent_id=profile.agent_id,
            agent_name=profile.name,
            provider=loop_result.provider,
            model=loop_result.model,
            task_type=profile.task_type,
            session_id=payload.session_id,
            attempted_models=loop_result.attempted_models,
            response=loop_result.response,
        )

    def _invoke_loop_tool(
        self,
        agent_id: str,
        profile: AgentProfileResponse,
        tool_name: str,
        arguments: dict[str, object],
    ) -> tuple[str, list[tuple[str, str]]]:
        side_effects: list[tuple[str, str]] = []
        self._ensure_tool_allowed(agent_id, tool_name)
        if tool_name == "web_automation" and not profile.allow_online:
            raise AgentOnlineError(f"Agent '{profile.name}' is not configured for online execution.")
        built = build_tool_arguments(tool_name, arguments)
        if tool_name == "list_files":
            result = self._tooling.list_files(built)
        elif tool_name == "read_file":
            result = self._tooling.read_file(built)
        elif tool_name == "execute_command":
            result = self._tooling.execute_command(built)
        elif tool_name == "apply_patch":
            result = self._tooling.apply_patch(built)
            if result.applied and self._verify_after_patch and self._verify_cmd:
                verify_result = self._tooling.execute_command(
                    ExecuteCommandRequest(
                        command=self._verify_cmd,
                        path=".",
                        dry_run=False,
                        confirmed=True,
                    )
                )
                side_effects.append(
                    (
                        "patch_verify",
                        (
                            f"Verify after patch: exit_code={verify_result.exit_code}, "
                            f"executed={verify_result.executed}, "
                            f"stdout={(verify_result.stdout or verify_result.stderr)[:300]}"
                        ),
                    )
                )
                return (
                    json.dumps(
                        {
                            "patch": result.model_dump(mode="json"),
                            "verify": verify_result.model_dump(mode="json"),
                        },
                        ensure_ascii=True,
                    ),
                    side_effects,
                )
        elif tool_name == "web_automation":
            result = self._browser_workflow.run(built)
        else:
            raise AgentPermissionError(f"Unsupported loop tool: {tool_name}")
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=True), side_effects

    def _run_online_request(
        self,
        profile: AgentProfileResponse,
        payload: AgentRunRequest,
    ) -> AgentRunResponse:
        if not profile.allow_online:
            raise AgentOnlineError(f"Agent '{profile.name}' does not allow online workflows.")
        if "web_automation" not in set(profile.enabled_tools):
            raise AgentPermissionError(
                f"Agent '{profile.name}' is not allowed to use tool 'web_automation'."
            )

        objective = payload.online_objective or payload.input
        web_result = self._browser_workflow.run(
            WebAutomationRequest(
                url=payload.online_url or "",
                objective=objective,
                max_steps=profile.online_max_steps,
                timeout_seconds=profile.online_timeout_seconds,
                capture_links_limit=profile.online_capture_links_limit,
            )
        )
        response_text = self._format_online_response(web_result)
        return AgentRunResponse(
            agent_id=profile.agent_id,
            agent_name=profile.name,
            provider="automation",
            model="web_automation",
            task_type=profile.task_type,
            session_id=payload.session_id,
            attempted_models=["web_automation"],
            response=response_text,
        )

    @staticmethod
    def _format_online_response(result: WebAutomationResponse) -> str:
        lines = [
            f"Online objective: {result.objective}",
            f"Success: {result.success}",
            f"Blocker: {result.blocker_detected}",
        ]
        if result.blocker_reason:
            lines.append(f"Blocker reason: {result.blocker_reason}")
        if result.evidence is not None:
            lines.extend(
                [
                    f"Requested URL: {result.evidence.requested_url}",
                    f"Final URL: {result.evidence.final_url}",
                    f"Status code: {result.evidence.status_code}",
                    f"Title: {result.evidence.title or 'n/a'}",
                    f"Captured links: {len(result.evidence.links)}",
                ]
            )
        lines.append("Steps:")
        for step in result.steps:
            lines.append(f"- {step}")
        return "\n".join(lines)

    def _ensure_tool_allowed(self, agent_id: str, tool_name: str) -> None:
        profile = self.get_agent(agent_id)
        if tool_name not in set(profile.enabled_tools):
            raise AgentPermissionError(
                f"Agent '{profile.name}' is not allowed to use tool '{tool_name}'."
            )

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                run_id, agent_id, payload = self._run_queue.get(timeout=0.5)
            except Empty:
                continue
            try:
                self._process_run(run_id, agent_id, payload)
            finally:
                self._run_queue.task_done()

    def _process_run(self, run_id: str, agent_id: str, payload: AgentRunRequest) -> None:
        # Detailed lifecycle note:
        # 1) Worker dequeues a run and performs a fresh lookup from persistent store.
        # 2) If run was cancelled while waiting in queue, worker exits without side effects.
        # 3) State transitions to "running" are persisted before execution starts, so
        #    external pollers/SSE clients can observe progress immediately.
        # 4) Execution happens outside the lock (chat or web workflow) to avoid blocking
        #    other queue operations and reads.
        # 5) Before final write, worker re-reads run state; if run became cancelled during
        #    execution, terminal write is skipped to preserve user intent.
        # 6) Terminal states ("completed"/"failed") are always persisted with updated_at,
        #    provider/model metadata, response, and error when available.
        # This ordering guarantees deterministic observable state transitions and prevents
        # stale in-memory snapshots from overwriting newer cancellation decisions.
        for attempt in range(1, self._run_max_attempts + 1):
            with self._lock:
                current = self._run_store.get_run(run_id)
                if current is None:
                    return
                if current.state == AgentRunState.cancelled:
                    return
                current.state = AgentRunState.running
                current.attempts = attempt
                current.updated_at = _utc_now_iso()
                self._run_store.put_run(current)
                self._append_event(
                    run_id=run_id,
                    event_type="run_attempt_started",
                    state=AgentRunState.running,
                    message=f"Run attempt {attempt}/{self._run_max_attempts} started.",
                    attempt=attempt,
                )

            try:
                profile = self.get_agent(agent_id)
                result = asyncio.run(
                    self._run_with_profile(profile, payload, run_id=run_id, attempt=attempt)
                )
                with self._lock:
                    current = self._run_store.get_run(run_id)
                    if current is None or current.state == AgentRunState.cancelled:
                        return
                    current.state = AgentRunState.completed
                    current.updated_at = _utc_now_iso()
                    current.provider = result.provider
                    current.model = result.model
                    current.attempted_models = result.attempted_models
                    current.response = self._truncate_response(result.response)
                    current.session_id = result.session_id
                    current.error = None
                    current.failure_class = None
                    self._run_store.put_run(current)
                    self._append_event(
                        run_id=run_id,
                        event_type="run_completed",
                        state=AgentRunState.completed,
                        message="Run completed successfully.",
                        attempt=attempt,
                    )
                    if profile.use_long_term_memory and self._agent_memory is not None:
                        self._agent_memory.append(
                            agent_id=agent_id,
                            outcome="completed",
                            summary=payload.input[:120],
                            detail=current.response[:500],
                            run_id=run_id,
                        )
                    if self._training_signals is not None:
                        events = self._run_store.get_events(run_id, limit=40)
                        trajectory = "\n".join(
                            f"[{event.event_type}] {event.message}"
                            for event in events
                            if event.message.strip()
                        )
                        self._training_signals.try_capture_agent_run(
                            run_id=run_id,
                            instruction=payload.input,
                            response=current.response,
                            session_id=current.session_id,
                            trajectory=trajectory,
                        )
                return
            except Exception as exc:  # noqa: BLE001
                failure_class = self._classify_failure(exc)
                is_last = attempt >= self._run_max_attempts
                with self._lock:
                    current = self._run_store.get_run(run_id)
                    if current is None:
                        return
                    current.updated_at = _utc_now_iso()
                    current.error = str(exc)
                    current.failure_class = failure_class
                    if is_last:
                        current.state = AgentRunState.failed
                        self._run_store.put_run(current)
                        self._append_event(
                            run_id=run_id,
                            event_type="run_dead_lettered",
                            state=AgentRunState.failed,
                            message=(
                                f"Run failed after {self._run_max_attempts} attempts: "
                                f"{failure_class}: {exc}"
                            ),
                            attempt=attempt,
                        )
                        return

                    self._run_store.put_run(current)
                    self._append_event(
                        run_id=run_id,
                        event_type="run_retry_scheduled",
                        state=AgentRunState.running,
                        message=f"Attempt {attempt} failed ({failure_class}). Scheduling retry.",
                        attempt=attempt,
                    )
                if self._run_retry_backoff_ms > 0:
                    time.sleep((self._run_retry_backoff_ms * (2 ** (attempt - 1))) / 1000.0)

    @staticmethod
    def _classify_failure(exc: Exception) -> str:
        if isinstance(exc, AgentLoopError):
            return "loop_error"
        if isinstance(exc, AgentOnlineError):
            return "online_error"
        if isinstance(exc, AgentPermissionError):
            return "permission_error"
        if isinstance(exc, AgentNotFoundError):
            return "agent_not_found"
        return "execution_error"

    def _append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        state: AgentRunState,
        message: str,
        attempt: int,
    ) -> None:
        self._run_store.append_event(
            run_id=run_id,
            event=AgentRunEvent(
                event_type=event_type,
                state=state,
                message=message,
                timestamp=_utc_now_iso(),
                attempt=attempt,
            ),
        )
        self._run_store.trim_events(run_id=run_id, max_events=self._max_events_per_run)

    def _truncate_response(self, text: str) -> str:
        if len(text) <= self._max_response_chars:
            return text
        marker = "\n\n[response truncated by retention policy]"
        safe = max(0, self._max_response_chars - len(marker))
        return text[:safe] + marker
