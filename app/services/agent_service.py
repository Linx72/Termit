from __future__ import annotations

import asyncio
import json
from contextvars import ContextVar
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
    AgentRunConfirmResponse,
    AgentRunCreateResponse,
    AgentRunResumeResponse,
    AgentRunEvent,
    AgentRunLifecycleUpdate,
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
from app.services.agent_activity_events import (
    activity_summary_from_events,
    events_for_loop_step,
)
from app.services.agent_policy_preset_service import AgentPolicyPresetService
from app.services.agent_registry_store import AgentRegistryStore
from app.services.agent_run_store import AgentRunStore
from app.services.agent_run_queue import AgentRunQueue
from app.services.agent_hook_service import AgentHookService, HookEvent
from app.services.agent_loop_service import (
    AgentAwaitingConfirmation,
    AgentLoopError,
    AgentLoopService,
    build_tool_arguments,
)
from app.services.agent_memory_store import AgentMemoryStore
from app.services.agent_outcome_service import classify_agent_outcome
from app.services.agent_run_notifier import AgentRunNotifier
from app.services.build_workflow_service import BuildWorkflowService
from app.services.ssh_workspace_service import SshWorkspaceConfig, SshWorkspaceService
from app.services.browser_workflow_service import BrowserWorkflowService
try:
    from app.services.playwright_browser_service import PlaywrightBrowserService, PlaywrightUnavailableError  # noqa: F401
except ImportError:
    PlaywrightBrowserService = None  # type: ignore[assignment]
    PlaywrightUnavailableError = RuntimeError  # type: ignore[assignment,misc]
from app.services.chat_service import ChatService
from app.services.context_enrichment_service import ContextEnrichmentService
from app.services.guardrail_service import GuardrailService
from app.services.json_safe import json_dumps, json_safe
from app.services.mcp_registry_service import McpRegistryService
from app.services.search_provider import SearchProvider, StubSearchProvider
from app.services.skill_store import SkillStore
from app.services.skill_selector_service import SkillSelectorService, SkillSelectionResult
from app.services.tooling_service import ToolingService
from app.services.trace_span_store import TraceSpanStore
from app.services.training_signal_store import TrainingSignalStore, normalize_capture_instruction
from app.services.patch_outcome_store import PatchOutcomeStore
from app.services.agent_tool_schema import (
    build_openai_tools,
    build_tool_schema_response,
    deferred_tool_catalog,
    expand_tools_after_use,
    resolve_described_tools,
    select_initial_tool_names,
)
from app.services.loop_step_budget import resolve_loop_step_budget
from app.services.repo_profile_resolver import infer_repo_profile_id
from app.services.verify_command_resolver import resolve_verify_command


class AgentNotFoundError(Exception):
    pass


class AgentRunNotFoundError(Exception):
    pass


class AgentQueueFullError(Exception):
    pass


class AgentDrainingError(Exception):
    pass


class AgentPermissionError(Exception):
    pass


class AgentOnlineError(Exception):
    pass


class GuardrailBlockedError(Exception):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_RISKY_LOOP_TOOLS = frozenset({"apply_patch", "execute_command", "browser_click"})
_ASK_BLOCKED_TOOLS = frozenset(
    {
        "apply_patch",
        "execute_command",
        "browser_click",
        "spawn_agent",
        "web_automation",
        "mcp_invoke",
    }
)
_POLICY_FALLBACK_FAILURE_CLASSES = frozenset(
    {
        "tool_error",
        "parse_error",
        "verification_error",
        "step_limit",
        "loop_error",
    }
)
_POLICY_FALLBACK_HINT = (
    "\n\n[Policy fallback] Previous attempt degraded; continue read-only with a concise plan "
    "and safe steps (dry-run commands only)."
)
_active_ssh_config: ContextVar[SshWorkspaceConfig | None] = ContextVar(
    "active_ssh_config", default=None
)


class AgentService:
    def __init__(
        self,
        chat_service: ChatService,
        registry: AgentRegistryStore,
        run_store: AgentRunStore,
        tooling: ToolingService,
        browser_workflow: BrowserWorkflowService,
        playwright_browser: Optional[PlaywrightBrowserService] = None,
        agent_memory_store: Optional[AgentMemoryStore] = None,
        agent_loop_service: Optional[AgentLoopService] = None,
        max_concurrency: int = 2,
        max_queue_size: int = 100,
        run_max_attempts: int = 2,
        run_retry_backoff_ms: int = 250,
        run_timeout_seconds: int = 180,
        queue_stuck_timeout_seconds: int = 120,
        max_events_per_run: int = 500,
        max_response_chars: int = 12000,
        retention_days: int = 14,
        training_signal_store: Optional[TrainingSignalStore] = None,
        patch_outcome_store: Optional[PatchOutcomeStore] = None,
        verify_after_patch: bool = False,
        verify_cmd: str = "",
        verify_max_retries: int = 1,
        auto_confirm_risky_tools: bool = False,
        guardrail_service: Optional[GuardrailService] = None,
        hook_service: Optional[AgentHookService] = None,
        skill_store: Optional[SkillStore] = None,
        skill_selector: Optional[SkillSelectorService] = None,
        search_provider: Optional[SearchProvider] = None,
        mcp_registry: Optional[McpRegistryService] = None,
        trace_span_store: Optional[TraceSpanStore] = None,
        context_enrichment: Optional[ContextEnrichmentService] = None,
        guardrails_enabled: bool = True,
        default_repo_profile_id: Optional[str] = None,
        policy_preset_service: Optional[AgentPolicyPresetService] = None,
        media_generation_service: Optional[object] = None,
        reasoning_orchestrator: Optional[object] = None,
        tool_loop_metrics_recent_days: int = 7,
        tool_loop_metrics_recent_run_window: int = 5,
        lazy_tool_schemas_enabled: bool = True,
        cache_aware_routing_enabled: bool = True,
    ) -> None:
        self._chat_service = chat_service
        self._registry = registry
        self._run_store = run_store
        self._tooling = tooling
        self._browser_workflow = browser_workflow
        self._playwright_browser = playwright_browser
        self._agent_memory = agent_memory_store
        self._loop_service = agent_loop_service or AgentLoopService()
        self._run_queue: AgentRunQueue[tuple[str, str, AgentRunRequest]] = AgentRunQueue(
            maxsize=max(1, max_queue_size)
        )
        self._run_max_attempts = max(1, run_max_attempts)
        self._run_retry_backoff_ms = max(0, run_retry_backoff_ms)
        self._run_timeout_seconds = max(10, run_timeout_seconds)
        self._queue_stuck_timeout_seconds = max(10, queue_stuck_timeout_seconds)
        self._max_events_per_run = max(1, max_events_per_run)
        self._max_response_chars = max(256, max_response_chars)
        self._retention_days = max(1, retention_days)
        self._training_signals = training_signal_store
        self._patch_outcomes = patch_outcome_store
        self._verify_after_patch = verify_after_patch
        self._verify_cmd = verify_cmd.strip()
        self._verify_max_retries = max(0, verify_max_retries)
        self._auto_confirm_risky_tools = auto_confirm_risky_tools
        self._guardrails = guardrail_service
        self._guardrails_enabled = guardrails_enabled
        self._hooks = hook_service
        self._skills = skill_store
        self._skill_selector = skill_selector
        self._search = search_provider or StubSearchProvider()
        self._mcp = mcp_registry
        self._trace_spans = trace_span_store
        self._context_enrichment = context_enrichment
        self._default_repo_profile_id = (default_repo_profile_id or "").strip() or None
        self._policy_presets = policy_preset_service
        self._media = media_generation_service
        self._reasoning_orchestrator = reasoning_orchestrator
        self._tool_loop_metrics_recent_days = max(0, tool_loop_metrics_recent_days)
        self._tool_loop_metrics_recent_run_window = max(0, tool_loop_metrics_recent_run_window)
        self._lazy_tool_schemas_enabled = lazy_tool_schemas_enabled
        self._cache_aware_routing_enabled = cache_aware_routing_enabled
        self._ssh = SshWorkspaceService(tooling)
        self._notifier = AgentRunNotifier.get()
        self._queue_capacity = max(1, max_queue_size)
        self._worker_count = max(1, max_concurrency)
        self._lock = Lock()
        self._workers: list[Thread] = []
        self._stop = Event()
        self._draining = False
        self.start()

    def start(self) -> None:
        self._draining = False
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

    def stop(self, grace_seconds: float = 30.0) -> dict[str, object]:
        """Stop workers; wait up to grace_seconds for in-flight runs to finish."""
        self._draining = True
        self._stop.set()
        deadline = time.monotonic() + max(0.0, grace_seconds)
        while time.monotonic() < deadline:
            with self._lock:
                by_state = self._run_store.count_runs_by_state()
            running = int(by_state.get(AgentRunState.running.value, 0))
            if running == 0 and self._run_queue.qsize() == 0:
                break
            time.sleep(0.25)
        for worker in list(self._workers):
            remaining = max(0.05, deadline - time.monotonic())
            worker.join(timeout=remaining)
        self._workers = []
        with self._lock:
            running_left = int(
                self._run_store.count_runs_by_state().get(AgentRunState.running.value, 0)
            )
        return {
            "draining": self._draining,
            "running_left": running_left,
            "queue_size": self._run_queue.qsize(),
        }

    def is_draining(self) -> bool:
        return self._draining

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
        if self._draining:
            raise AgentDrainingError("Agent service is shutting down; new runs are not accepted.")
        profile = self.get_agent(agent_id)
        if self._guardrails_enabled and self._guardrails is not None:
            check = self._guardrails.check_prompt(payload.input)
            if not check.allowed:
                raise GuardrailBlockedError(check.reason)
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
            parent_run_id=payload.parent_run_id,
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

    def list_child_runs(self, parent_run_id: str, limit: int = 50) -> AgentRunListResponse:
        safe_limit = max(1, min(limit, 200))
        with self._lock:
            all_runs = self._run_store.list_runs(limit=5000)
        children = [run for run in all_runs if (run.parent_run_id or "").strip() == parent_run_id]
        children.sort(key=lambda item: item.updated_at, reverse=True)
        selected = children[:safe_limit]
        return AgentRunListResponse(runs=selected, total=len(children))

    def list_all_runs(self, limit: int = 100, lifecycle_status: str | None = None) -> AgentRunListResponse:
        safe_limit = max(1, min(limit, 200))
        with self._lock:
            selected = self._run_store.list_all_runs(limit=safe_limit, lifecycle_status=lifecycle_status)
        return AgentRunListResponse(runs=selected, total=len(selected))

    def set_lifecycle_status(self, run_id: str, lifecycle_status: str) -> bool:
        with self._lock:
            return self._run_store.set_lifecycle_status(run_id, lifecycle_status)

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
            runs = self._run_store.list_runs(limit=5000)
        now_ts = datetime.now(timezone.utc).timestamp()
        stale_queued = 0
        stale_running = 0
        max_queued_age = 0.0
        max_running_age = 0.0
        timeout_runs_total = 0
        completed_runs_total = 0
        terminal_runs_total = 0
        by_outcome_class: dict[str, int] = {}
        for run in runs:
            if run.failure_class == "run_timeout":
                timeout_runs_total += 1
            if run.state in {AgentRunState.completed, AgentRunState.failed, AgentRunState.cancelled}:
                terminal_runs_total += 1
                outcome = run.outcome_class or classify_agent_outcome(
                    state=run.state.value,
                    failure_class=run.failure_class,
                    response=run.response or "",
                    error=run.error,
                )
                by_outcome_class[outcome] = by_outcome_class.get(outcome, 0) + 1
            if run.state == AgentRunState.completed:
                completed_runs_total += 1
            if run.state not in {AgentRunState.queued, AgentRunState.running}:
                continue
            age = self._safe_run_age_seconds(run.updated_at, now_ts)
            if run.state == AgentRunState.queued:
                max_queued_age = max(max_queued_age, age)
                if age >= self._queue_stuck_timeout_seconds:
                    stale_queued += 1
            elif run.state == AgentRunState.running:
                max_running_age = max(max_running_age, age)
                if age >= self._queue_stuck_timeout_seconds:
                    stale_running += 1
        active_runs = int(by_state.get(AgentRunState.running.value, 0))
        utilization = round((queue_size / self._queue_capacity) * 100, 2)
        lifecycle_stale_total = stale_queued + stale_running
        lifecycle_completion_rate = (
            round(completed_runs_total / terminal_runs_total, 4) if terminal_runs_total > 0 else 0.0
        )
        metrics: dict[str, object] = {
            "queue_size": queue_size,
            "queue_capacity": self._queue_capacity,
            "queue_utilization_percent": utilization,
            "worker_count": self._worker_count,
            "alive_workers": alive_workers,
            "total_runs": total_runs,
            "by_state": by_state,
            "active_runs": active_runs,
            "stale_queued_runs": stale_queued,
            "stale_running_runs": stale_running,
            "lifecycle_stale_total": lifecycle_stale_total,
            "lifecycle_terminal_runs_total": terminal_runs_total,
            "lifecycle_completed_runs_total": completed_runs_total,
            "lifecycle_timeout_runs_total": timeout_runs_total,
            "lifecycle_completion_rate": lifecycle_completion_rate,
            "max_queued_age_seconds": round(max_queued_age, 2),
            "max_running_age_seconds": round(max_running_age, 2),
            "queue_stuck_timeout_seconds": self._queue_stuck_timeout_seconds,
            "by_outcome_class": by_outcome_class,
        }
        metrics.update(self._run_store.tool_loop_event_metrics())
        if self._tool_loop_metrics_recent_days > 0:
            recent_tl = self._run_store.tool_loop_event_metrics(
                recent_days=self._tool_loop_metrics_recent_days
            )
            for key, value in recent_tl.items():
                metrics[f"{key}_recent"] = value
        if self._tool_loop_metrics_recent_run_window > 0:
            window_tl = self._run_store.tool_loop_event_metrics(
                recent_run_limit=self._tool_loop_metrics_recent_run_window
            )
            for key, value in window_tl.items():
                metrics[f"{key}_recent_window"] = value
        metrics.update(self._run_store.mcp_usage_metrics())
        return metrics

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

    def cleanup_stale_active_runs(
        self,
        *,
        stale_before_iso: str,
        dry_run: bool = False,
    ) -> dict[str, object]:
        stale_runs: list[AgentRunRecordResponse] = []
        with self._lock:
            for run in self._run_store.list_runs(limit=5000):
                if run.state not in {AgentRunState.running, AgentRunState.queued}:
                    continue
                if run.updated_at < stale_before_iso:
                    stale_runs.append(run)
            if not dry_run:
                for run in stale_runs:
                    run.state = AgentRunState.cancelled
                    run.updated_at = _utc_now_iso()
                    if not run.error:
                        run.error = "Cancelled stale run during maintenance."
                    self._run_store.put_run(run)
                    self._append_event(
                        run_id=run.run_id,
                        event_type="run_cancelled_stale",
                        state=AgentRunState.cancelled,
                        message="Run cancelled by maintenance due to staleness timeout.",
                        attempt=run.attempts,
                    )
                    self._publish_run(run)
            remaining = self._run_store.count_runs()
        return {
            "dry_run": dry_run,
            "stale_before": stale_before_iso,
            "cancelled_runs": len(stale_runs),
            "remaining_runs": remaining,
        }

    def cleanup_stuck_runs(
        self,
        *,
        dry_run: bool = False,
    ) -> dict[str, object]:
        """Завершает run'ы, зависшие в состоянии running дольше run_timeout_seconds * 2.

        В отличие от cleanup_stale_active_runs (порог 2 ч), этот метод
        нацелен на run'ы, worker-потоки которых заблокировались на
        синхронном вызове и не могут завершиться самостоятельно.
        """
        stuck_timeout = self._run_timeout_seconds * 2
        stuck_before = (
            datetime.now(tz=timezone.utc).timestamp() - stuck_timeout
        )
        stuck_before_iso = datetime.fromtimestamp(
            stuck_before, tz=timezone.utc
        ).isoformat()
        stuck_runs: list[AgentRunRecordResponse] = []
        with self._lock:
            for run in self._run_store.list_runs(limit=5000):
                if run.state != AgentRunState.running:
                    continue
                if run.lifecycle_status != "active":
                    continue
                if run.updated_at < stuck_before_iso:
                    stuck_runs.append(run)
            if not dry_run:
                for run in stuck_runs:
                    run.state = AgentRunState.failed
                    run.failure_class = "worker_timeout"
                    run.outcome_class = "failure"
                    run.updated_at = _utc_now_iso()
                    if not run.error:
                        run.error = (
                            f"Run stuck in running state for > {stuck_timeout}s "
                            "(worker blocked). Force-failed by maintenance."
                        )
                    self._run_store.put_run(run)
                    self._append_event(
                        run_id=run.run_id,
                        event_type="run_stuck_force_failed",
                        state=AgentRunState.failed,
                        message=run.error,
                        attempt=run.attempts,
                    )
                    self._publish_run(run)
            remaining = self._run_store.count_runs()
        return {
            "dry_run": dry_run,
            "stuck_before": stuck_before_iso,
            "stuck_timeout_seconds": stuck_timeout,
            "force_failed_runs": len(stuck_runs),
            "remaining_runs": remaining,
        }

    def cancel_run(self, run_id: str) -> AgentRunCancelResponse:
        with self._lock:
            record = self._run_store.get_run(run_id)
            if record is None:
                raise AgentRunNotFoundError(f"Agent run not found: {run_id}")
            if record.state in {AgentRunState.queued, AgentRunState.running}:
                previous_state = record.state
                record.state = AgentRunState.cancelled
                record.updated_at = _utc_now_iso()
                self._run_store.put_run(record)
                self._append_event(
                    run_id=run_id,
                    event_type="run_cancelled",
                    state=AgentRunState.cancelled,
                    message=(
                        "Run cancelled before execution."
                        if previous_state == AgentRunState.queued
                        else "Run cancelled during execution."
                    ),
                    attempt=record.attempts,
                )
                return AgentRunCancelResponse(run_id=run_id, cancelled=True, state=record.state)
            return AgentRunCancelResponse(run_id=run_id, cancelled=False, state=record.state)

    def confirm_run(self, run_id: str, approved: bool) -> AgentRunConfirmResponse:
        with self._lock:
            record = self._run_store.get_run(run_id)
            if record is None:
                raise AgentRunNotFoundError(f"Agent run not found: {run_id}")
            if record.state != AgentRunState.awaiting_confirmation:
                raise ValueError(f"Run {run_id} is not awaiting confirmation.")

            if not approved:
                record.state = AgentRunState.failed
                record.updated_at = _utc_now_iso()
                record.error = "User rejected risky tool."
                record.failure_class = "user_rejected"
                self._run_store.put_run(record)
                self._append_event(
                    run_id=run_id,
                    event_type="confirmation_rejected",
                    state=AgentRunState.failed,
                    message="User rejected risky tool.",
                    attempt=record.attempts,
                )
                self._publish_run(record)
                return AgentRunConfirmResponse(run_id=run_id, state=record.state, resumed=False)

            checkpoint = json.loads(record.checkpoint_json or "{}")
            pending_args = checkpoint.get("pending_arguments", {})
            if isinstance(pending_args, dict):
                pending_args["confirmed"] = True
                checkpoint["pending_arguments"] = pending_args
            record.checkpoint_json = json_dumps(checkpoint, ensure_ascii=True)
            record.state = AgentRunState.queued
            record.updated_at = _utc_now_iso()
            self._run_store.put_run(record)
            self._append_event(
                run_id=run_id,
                event_type="confirmation_approved",
                state=AgentRunState.queued,
                message="User approved risky tool; resuming run.",
                attempt=record.attempts,
            )
            self._publish_run(record)
            payload = AgentRunRequest(
                input=record.input,
                session_id=record.session_id,
                resume_checkpoint=checkpoint,
            )

        try:
            self._run_queue.put_nowait((run_id, record.agent_id, payload), priority=0)
        except Full as exc:
            raise AgentQueueFullError("Agent execution queue is full.") from exc
        return AgentRunConfirmResponse(run_id=run_id, state=AgentRunState.queued, resumed=True)

    def resume_run(self, run_id: str) -> AgentRunResumeResponse:
        with self._lock:
            record = self._run_store.get_run(run_id)
            if record is None:
                raise AgentRunNotFoundError(f"Agent run not found: {run_id}")
            if not record.checkpoint_json:
                raise ValueError(f"Run {run_id} has no checkpoint to resume.")
            if record.state not in {AgentRunState.failed, AgentRunState.cancelled, AgentRunState.awaiting_confirmation}:
                raise ValueError(f"Run {run_id} is not resumable from state {record.state.value}.")
            checkpoint = json.loads(record.checkpoint_json)
            record.state = AgentRunState.queued
            record.updated_at = _utc_now_iso()
            record.error = None
            self._run_store.put_run(record)
            self._append_event(
                run_id=run_id,
                event_type="run_resumed",
                state=AgentRunState.queued,
                message="Run resumed from checkpoint.",
                attempt=record.attempts,
            )
            self._publish_run(record)
            payload = AgentRunRequest(
                input=record.input,
                session_id=record.session_id,
                resume_checkpoint=checkpoint,
            )

        try:
            self._run_queue.put_nowait((run_id, record.agent_id, payload), priority=0)
        except Full as exc:
            raise AgentQueueFullError("Agent execution queue is full.") from exc
        return AgentRunResumeResponse(run_id=run_id, state=AgentRunState.queued, resumed=True)

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

    def _run_path_prefix(self, profile: AgentProfileResponse, payload: AgentRunRequest) -> str:
        return (
            payload.retrieval_path_prefix
            or profile.retrieval_path_prefix
            or payload.workspace_scope
            or ""
        ).strip()

    def _resolve_repo_profile_id(
        self,
        profile: AgentProfileResponse,
        payload: AgentRunRequest,
    ) -> str | None:
        router = getattr(self._chat_service, "model_router", None)
        routing_policy = getattr(router, "_routing_policy", None) if router is not None else None
        list_profiles_fn = routing_policy.list_repo_profiles if routing_policy is not None else list
        return infer_repo_profile_id(
            explicit=payload.repo_profile,
            path_prefix=self._run_path_prefix(profile, payload),
            default_profile_id=self._default_repo_profile_id,
            list_profiles_fn=list_profiles_fn,
        )

    def _resolve_run_model(
        self,
        profile: AgentProfileResponse,
        payload: AgentRunRequest,
    ) -> tuple[str, list[str] | None]:
        requested = (payload.model or "").strip()
        if requested:
            return requested, None
        repo_profile = self._resolve_repo_profile_id(profile, payload)
        path_prefix = self._run_path_prefix(profile, payload)
        router = getattr(self._chat_service, "model_router", None)
        if router is None:
            fallback = profile.model or "default"
            return fallback, None
        candidates = router.candidate_models(
            profile.task_type,
            profile.model,
            message=payload.input,
            repo_profile=repo_profile,
            path_prefix=path_prefix,
        )
        if candidates:
            return candidates[0], (candidates[1:] if len(candidates) > 1 else None)
        return router.select_model(profile.task_type, profile.model), None

    def _resolve_ssh_config(self, payload: AgentRunRequest) -> SshWorkspaceConfig | None:
        mode = (payload.execution_mode or "local").strip().lower()
        cfg = SshWorkspaceService.from_run_payload(
            ssh_host=payload.ssh_host,
            ssh_user=payload.ssh_user,
            ssh_remote_path=payload.ssh_remote_path,
            ssh_port=payload.ssh_port,
            ssh_identity=payload.ssh_identity,
        )
        if cfg is None:
            return None
        if mode in {"ssh", "hybrid"}:
            return cfg
        return None

    def _prepare_run_payload(
        self,
        profile: AgentProfileResponse,
        payload: AgentRunRequest,
    ) -> tuple[AgentProfileResponse, AgentRunRequest]:
        updated_profile = profile
        updated_payload = payload
        if BuildWorkflowService.is_build_task(payload.input):
            cfg = SshWorkspaceService.from_run_payload(
                ssh_host=payload.ssh_host,
                ssh_user=payload.ssh_user,
                ssh_remote_path=payload.ssh_remote_path,
                ssh_port=payload.ssh_port,
                ssh_identity=payload.ssh_identity,
            )
            ssh_label = f"{cfg.user}@{cfg.host}:{cfg.remote_path}" if cfg else ""
            workspace = (
                payload.workspace_scope
                or payload.retrieval_path_prefix
                or str(self._tooling.root)
            )
            enriched = BuildWorkflowService.enrich_agent_input(
                payload.input,
                execution_mode=payload.execution_mode or "local",
                workspace=workspace,
                ssh_label=ssh_label,
            )
            updated_payload = payload.model_copy(update={"input": enriched})
        mode = (payload.execution_mode or "local").strip().lower()
        if mode in {"hybrid", "online"} and profile.allow_online is False:
            if BuildWorkflowService.is_build_task(payload.input) or mode == "online":
                updated_profile = profile.model_copy(update={"allow_online": True})
        return updated_profile, updated_payload

    @staticmethod
    def _capture_instruction(payload: AgentRunRequest) -> str:
        """Short task text for training-signal capture (not builder/system prompt)."""
        objective = (payload.online_objective or "").strip()
        if objective:
            return normalize_capture_instruction(objective)
        task = BuildWorkflowService.extract_user_task(payload.input)
        return normalize_capture_instruction(task)

    def _apply_run_mode(
        self,
        profile: AgentProfileResponse,
        payload: AgentRunRequest,
    ) -> tuple[AgentProfileResponse, AgentRunRequest]:
        mode = (payload.run_mode or "agent").strip().lower()
        if mode != "ask":
            return profile, payload
        allowed = [tool for tool in profile.enabled_tools if tool not in _ASK_BLOCKED_TOOLS]
        ask_profile = profile.model_copy(
            update={
                "enabled_tools": allowed,
                "system_prompt": (
                    f"{profile.system_prompt}\n\n"
                    "[Ask mode] Read-only tools only — no apply_patch, execute_command, "
                    "spawn_agent, web_automation, or mcp_invoke."
                ),
            }
        )
        return ask_profile, payload

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

        profile, payload = self._apply_run_mode(profile, payload)

        if self._policy_presets is not None:
            profile, payload = self._policy_presets.apply_to_run(profile, payload)

        profile, payload = self._prepare_run_payload(profile, payload)
        ssh_token = _active_ssh_config.set(self._resolve_ssh_config(payload))

        use_loop = (
            profile.use_tool_loop
            if payload.use_tool_loop is None
            else payload.use_tool_loop
        )
        if use_loop:
            try:
                return await self._run_with_tool_loop(
                    profile,
                    payload,
                    run_id=run_id,
                    attempt=attempt,
                )
            finally:
                _active_ssh_config.reset(ssh_token)

        _active_ssh_config.reset(ssh_token)
        resolved_model, _escalation = self._resolve_run_model(profile, payload)
        skill_selection = self._resolve_mounted_skills(profile, payload)
        system_prompt = profile.system_prompt
        pinned_ids: frozenset[str] = frozenset()
        if skill_selection is not None:
            pinned_ids = frozenset(
                item.skill_id for item in skill_selection.selections if item.source == "pinned"
            )
        if skill_selection is not None and skill_selection.selected_skill_ids:
            profile_with_skills = self._append_skill_block(
                profile,
                skill_selection.selected_skill_ids,
                pinned_skill_ids=pinned_ids,
            )
            system_prompt = profile_with_skills.system_prompt
        chat_request = ChatRequest(
            message=payload.input,
            task_type=profile.task_type,
            model=resolved_model,
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
            history=[ChatMessage(role="system", content=system_prompt)],
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

    def _resolve_mounted_skills(
        self,
        profile: AgentProfileResponse,
        payload: AgentRunRequest,
    ) -> SkillSelectionResult | None:
        if self._skill_selector is None or self._skills is None:
            return None

        pinned: list[str] = []
        pinned.extend(profile.skill_ids)
        pinned.extend(payload.skill_ids)
        if self._context_enrichment is not None:
            pinned.extend(self._context_enrichment.list_project_skill_ids(payload.project_id))

        auto_enabled = (
            payload.auto_select_skills
            if payload.auto_select_skills is not None
            else self._skill_selector.enabled
        )
        return self._skill_selector.select_skills(
            instruction=payload.input,
            task_type=profile.task_type,
            pinned_skill_ids=pinned,
            changed_files=list(payload.changed_files),
            auto_select_enabled=auto_enabled,
        )

    def _append_skill_block(
        self,
        profile: AgentProfileResponse,
        skill_ids: list[str],
        *,
        pinned_skill_ids: frozenset[str] | None = None,
    ) -> AgentProfileResponse:
        if not skill_ids or self._skills is None:
            return profile
        discovery = self._skills.build_discovery_block()
        skill_block = self._skills.build_prompt_block(
            skill_ids,
            full_body_skill_ids=pinned_skill_ids,
        )
        if not skill_block:
            return profile
        parts = [profile.system_prompt]
        if discovery:
            parts.append(discovery)
        parts.append(skill_block)
        return profile.model_copy(update={"system_prompt": "\n\n".join(parts)})

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
            scope = payload.workspace_scope or payload.retrieval_path_prefix or None
            memory_context = self._agent_memory.get_context_for_task(
                profile.agent_id,
                task_hint=payload.input,
                workspace_scope=scope,
            )

        resolved_model, escalation_models = self._resolve_run_model(profile, payload)
        profile_for_loop = profile.model_copy(update={"model": resolved_model})

        skill_selection = self._resolve_mounted_skills(profile, payload)
        pinned_ids: frozenset[str] = frozenset()
        if skill_selection is not None:
            pinned_ids = frozenset(
                item.skill_id for item in skill_selection.selections if item.source == "pinned"
            )
        if skill_selection is not None and skill_selection.selected_skill_ids:
            profile_for_loop = self._append_skill_block(
                profile_for_loop,
                skill_selection.selected_skill_ids,
                pinned_skill_ids=pinned_ids,
            )
            if run_id:
                self._append_event(
                    run_id=run_id,
                    event_type="skills_mounted",
                    state=AgentRunState.running,
                    message=json_dumps(
                        {
                            "skill_ids": skill_selection.selected_skill_ids,
                            "selections": skill_selection.to_dict()["selections"],
                        },
                        ensure_ascii=False,
                    ),
                    attempt=attempt,
                )

        from app.services.cross_platform_dev_service import CrossPlatformDevService

        if CrossPlatformDevService.is_cross_platform_task(payload.input):
            cp_service = CrossPlatformDevService()
            cp_block = cp_service.build_agent_context(payload.input)
            profile_for_loop = profile_for_loop.model_copy(
                update={"system_prompt": f"{profile_for_loop.system_prompt}\n\n{cp_block}"}
            )

        if self._context_enrichment is not None:
            enrichment_lines = await self._context_enrichment.build_agent_context_lines(payload, profile)
            if enrichment_lines:
                memory_context = enrichment_lines + memory_context

        if (
            payload.mcp_context_inject is not False
            and self._mcp is not None
            and {"mcp_invoke", "mcp_read_resource", "mcp_get_prompt"} & set(profile_for_loop.enabled_tools)
        ):
            from app.services.mcp_context_service import McpContextService

            mcp_service = McpContextService(self._mcp)
            mcp_lines = mcp_service.build_context_lines(profile_for_loop)
            if mcp_lines:
                memory_context = mcp_lines + memory_context
                if run_id:
                    self._append_event(
                        run_id=run_id,
                        event_type="mcp_context_injected",
                        state=AgentRunState.running,
                        message=json_dumps({"lines": len(mcp_lines)}, ensure_ascii=False),
                        attempt=attempt,
                    )

        run_mode = (payload.run_mode or "agent").strip().lower()
        if (
            run_mode == "plan"
            and payload.mcp_context_inject is not False
            and self._mcp is not None
            and {"mcp_invoke", "mcp_read_resource", "mcp_get_prompt"} & set(profile_for_loop.enabled_tools)
        ):
            from app.services.mcp_context_service import McpContextService

            prompt_lines = McpContextService(self._mcp).build_plan_prompt_lines(profile_for_loop)
            if prompt_lines:
                memory_context = prompt_lines + memory_context
                if run_id:
                    self._append_event(
                        run_id=run_id,
                        event_type="mcp_prompt_injected",
                        state=AgentRunState.running,
                        message=json_dumps({"lines": len(prompt_lines)}, ensure_ascii=False),
                        attempt=attempt,
                    )

        if run_mode == "plan" and self._reasoning_orchestrator is not None:
            try:
                reasoning = self._reasoning_orchestrator.run_reasoning_pass(task=payload.input)
                profile_for_loop = profile_for_loop.model_copy(
                    update={
                        "system_prompt": (
                            f"{profile_for_loop.system_prompt}\n\n{reasoning.memory_block()}"
                        )
                    }
                )
                if run_id:
                    self._append_event(
                        run_id=run_id,
                        event_type="reasoning_pass",
                        state=AgentRunState.running,
                        message=json_dumps(reasoning.as_dict(), ensure_ascii=False)[:4000],
                        attempt=attempt,
                    )
            except Exception as exc:  # noqa: BLE001
                if run_id:
                    self._append_event(
                        run_id=run_id,
                        event_type="reasoning_pass_skipped",
                        state=AgentRunState.running,
                        message=str(exc)[:500],
                        attempt=attempt,
                    )

        run_verify_after_patch = (
            payload.verify_after_patch
            if payload.verify_after_patch is not None
            else self._verify_after_patch
        )
        run_verify_max_retries = (
            payload.verify_max_retries
            if payload.verify_max_retries is not None
            else self._verify_max_retries
        )
        run_auto_confirm = (
            payload.auto_confirm_risky_tools
            if payload.auto_confirm_risky_tools is not None
            else self._auto_confirm_risky_tools
        )
        enabled_tools = list(profile_for_loop.enabled_tools or [])
        if self._lazy_tool_schemas_enabled and "describe_tools" not in enabled_tools:
            enabled_tools.append("describe_tools")
            profile_for_loop = profile_for_loop.model_copy(update={"enabled_tools": enabled_tools})
        if self._lazy_tool_schemas_enabled:
            active_tool_names = set(
                select_initial_tool_names(
                    enabled_tools,
                    payload.input,
                    run_mode=run_mode,
                    verify_after_patch=run_verify_after_patch,
                )
            )
            lazy_catalog = deferred_tool_catalog(enabled_tools, active_tool_names)
            if lazy_catalog:
                profile_for_loop = profile_for_loop.model_copy(
                    update={"system_prompt": f"{profile_for_loop.system_prompt}{lazy_catalog}"}
                )
            tools_schema = build_openai_tools(sorted(active_tool_names))
        else:
            active_tool_names = set(enabled_tools)
            tools_schema = build_openai_tools(enabled_tools)
        configured_verify = self._verify_cmd if run_verify_after_patch else ""
        verify_cmd = (
            resolve_verify_command(str(self._tooling.root), configured_verify)
            if run_verify_after_patch
            else ""
        )

        def verify_fn() -> tuple[bool, str]:
            if not verify_cmd:
                return True, "Verify skipped: no command configured."
            started = time.perf_counter()
            ssh_cfg = _active_ssh_config.get()
            if ssh_cfg is not None:
                result = self._ssh.execute_command(
                    ssh_cfg,
                    ExecuteCommandRequest(
                        command=verify_cmd,
                        path=".",
                        dry_run=False,
                        confirmed=True,
                    ),
                )
            else:
                result = self._tooling.execute_command(
                    ExecuteCommandRequest(
                        command=verify_cmd,
                        path=".",
                        dry_run=False,
                        confirmed=True,
                    )
                )
            detail = (result.stdout or result.stderr or "")[:500]
            ok = not result.executed or result.exit_code == 0
            if self._trace_spans is not None and run_id:
                self._trace_spans.record(
                    run_id=run_id,
                    name="verify.stage",
                    status="ok" if ok else "failed",
                    detail=detail,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            return ok, f"exit_code={result.exit_code}; {detail}"

        async def traced_chat_fn(request: ChatRequest):
            started = time.perf_counter()
            try:
                result = await self._chat_service.chat(request)
            except Exception as exc:
                if self._trace_spans is not None and run_id:
                    self._trace_spans.record(
                        run_id=run_id,
                        name="provider.unknown",
                        status="error",
                        detail=str(exc)[:500],
                        duration_ms=int((time.perf_counter() - started) * 1000),
                    )
                raise
            if self._trace_spans is not None and run_id:
                self._trace_spans.record(
                    run_id=run_id,
                    name=f"provider.{result.provider}",
                    status="ok",
                    detail=f"model={result.model}",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            return result

        async def native_chat_fn(request: ChatRequest):
            started = time.perf_counter()
            schema = build_openai_tools(sorted(active_tool_names))
            try:
                result = await self._chat_service.chat_with_tools(request, schema)
            except Exception as exc:
                if self._trace_spans is not None and run_id:
                    self._trace_spans.record(
                        run_id=run_id,
                        name="provider.unknown",
                        status="error",
                        detail=str(exc)[:500],
                        duration_ms=int((time.perf_counter() - started) * 1000),
                    )
                raise
            if self._trace_spans is not None and run_id:
                self._trace_spans.record(
                    run_id=run_id,
                    name=f"provider.{result.provider}",
                    status="ok",
                    detail=f"model={result.model}",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            return result

        def tool_fn(tool_name: str, arguments: dict[str, object]) -> str:
            started = time.perf_counter()
            try:
                observation, side_effects = self._invoke_loop_tool(
                    profile_for_loop.agent_id,
                    profile_for_loop,
                    tool_name,
                    arguments,
                    run_id=run_id,
                    auto_confirm_risky_tools=run_auto_confirm,
                    verify_after_patch=run_verify_after_patch,
                )
            except Exception as exc:
                if self._trace_spans is not None and run_id:
                    self._trace_spans.record(
                        run_id=run_id,
                        name=f"tool.{tool_name}",
                        status="error",
                        detail=str(exc),
                        duration_ms=int((time.perf_counter() - started) * 1000),
                    )
                raise
            if self._trace_spans is not None and run_id:
                self._trace_spans.record(
                    run_id=run_id,
                    name=f"tool.{tool_name}",
                    status="ok",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
            if self._hooks is not None and run_id:
                self._hooks.emit(
                    HookEvent(
                        event_type="tool.post_use",
                        run_id=run_id,
                        agent_id=profile.agent_id,
                        state=AgentRunState.running.value,
                        message=f"tool={tool_name}",
                        extra={"tool_name": tool_name, "arguments": json_safe(arguments)},
                    )
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
                    if event_type == "spawn_agent":
                        child_run_id = ""
                        for token in message.split():
                            if token.startswith("child_run_id="):
                                child_run_id = token.split("=", 1)[1].strip()
                                break
                        if child_run_id:
                            try:
                                child_events = self.get_run_events(child_run_id, limit=120)
                            except AgentRunNotFoundError:
                                child_events = []
                            for child_event in child_events:
                                self._append_event(
                                    run_id=run_id,
                                    event_type="spawn_agent_child_event",
                                    state=AgentRunState.running,
                                    message=(
                                        f"child_run_id={child_run_id} {child_event.event_type}: "
                                        f"{child_event.message}"
                                    ),
                                    attempt=attempt,
                                )
            if self._lazy_tool_schemas_enabled:
                if tool_name == "describe_tools":
                    active_tool_names.update(
                        expand_tools_after_use(
                            tool_name,
                            enabled_tools,
                            active_tool_names,
                            describe_request=resolve_described_tools(arguments, enabled_tools),
                        )
                    )
                else:
                    active_tool_names.update(
                        expand_tools_after_use(tool_name, enabled_tools, active_tool_names)
                    )
            return observation

        def on_step(step) -> None:  # type: ignore[no-untyped-def]
            if not run_id:
                return
            message = f"Step {step.step}: {step.action}"
            if step.tool:
                message += f" ({step.tool})"
            if step.action == "parse_error":
                event_type = "tool_loop_parse_error"
            elif step.action == "final":
                event_type = "tool_loop_final"
            elif step.action == "tool":
                if str(step.observation).startswith("Tool error"):
                    event_type = "tool_loop_tool_error"
                else:
                    event_type = "tool_loop_tool"
            elif step.action == "verify_failed":
                event_type = "tool_loop_verify_failed"
            elif step.action == "verify_pass":
                event_type = "tool_loop_verify_pass"
            elif step.action == "verify_retry":
                event_type = "verify_retry_scheduled"
            else:
                event_type = "tool_loop_step"
            self._append_event(
                run_id=run_id,
                event_type=event_type,
                state=AgentRunState.running,
                message=message,
                attempt=attempt,
            )
            if step.action == "tool" and step.tool and not str(step.observation).startswith("Tool error"):
                for act_type, act_msg, act_payload in events_for_loop_step(
                    tool=step.tool,
                    observation=str(step.observation or ""),
                    step_message=message,
                ):
                    self._append_event(
                        run_id=run_id,
                        event_type=act_type,
                        state=AgentRunState.running,
                        message=act_msg,
                        attempt=attempt,
                        payload=act_payload,
                    )
            trace_payload = json_dumps(
                {
                    "step": step.step,
                    "action": step.action,
                    "tool": step.tool or "",
                    "observation": str(step.observation or "")[:4000],
                    "assistant": "",
                },
                ensure_ascii=False,
            )
            self._append_event(
                run_id=run_id,
                event_type="tool_loop_trace",
                state=AgentRunState.running,
                message=trace_payload,
                attempt=attempt,
            )
            if self._trace_spans is not None:
                span_status = "ok"
                span_name = f"loop.step.{step.action}"
                if step.action == "verify_pass":
                    span_name = "verify.pass"
                elif step.action == "verify_failed":
                    span_name = "verify.failed"
                    span_status = "failed"
                elif step.action == "verify_retry":
                    span_name = "verify.retry"
                    span_status = "retry"
                elif step.action == "parse_error":
                    span_status = "error"
                elif step.action == "tool" and str(step.observation).startswith("Tool error"):
                    span_status = "error"
                self._trace_spans.record(
                    run_id=run_id,
                    name=span_name,
                    status=span_status,
                    detail=(step.tool or str(step.observation or ""))[:500],
                )
            if self._training_signals is not None:
                obs_text = str(step.observation or "")
                verified = False
                verify_failed = False
                try:
                    obs_data = json.loads(obs_text)
                    if isinstance(obs_data, dict):
                        verify = obs_data.get("verify")
                        if isinstance(verify, dict) and verify.get("executed"):
                            verified = int(verify.get("exit_code") or 0) == 0
                            verify_failed = not verified
                        if not verified and step.tool == "execute_command":
                            executed = obs_data.get("executed")
                            exit_code = obs_data.get("exit_code")
                            if executed and exit_code is not None:
                                verified = int(exit_code) == 0
                                verify_failed = not verified
                except json.JSONDecodeError:
                    verify_failed = "Patch verify failed" in obs_text

                if step.action == "tool" and step.tool == "apply_patch":
                    patch_path = self._extract_patch_path(obs_text)
                    chosen_patch = obs_text[:4000]
                    if self._patch_was_applied(obs_text) and self._patch_outcomes is not None and patch_path:
                        self._patch_outcomes.record_applied_patch(
                            run_id=run_id,
                            rel_path=patch_path,
                            root_path=str(self._tooling.root),
                            instruction=self._capture_instruction(payload),
                            chosen_patch=chosen_patch,
                        )
                    if verified:
                        self._training_signals.try_capture_tool_step(
                            run_id=run_id,
                            step=step.step,
                            action=step.action,
                            tool=step.tool,
                            observation=obs_text,
                            instruction=self._capture_instruction(payload),
                            verified=True,
                        )
                elif step.action == "tool" and step.tool == "execute_command" and verified:
                    self._training_signals.try_capture_tool_step(
                        run_id=run_id,
                        step=step.step,
                        action=step.action,
                        tool=step.tool,
                        observation=obs_text,
                        instruction=self._capture_instruction(payload),
                        verified=True,
                    )
                else:
                    is_error = step.action in {
                        "parse_error",
                        "repeat_blocked",
                    } or obs_text.startswith("Tool error")
                    if is_error or verify_failed:
                        reason = "verify_failed" if verify_failed else "tool_error"
                        self._training_signals.try_capture_negative_tool_step(
                            run_id=run_id,
                            step=step.step,
                            action=step.action,
                            tool=step.tool,
                            observation=obs_text,
                            instruction=self._capture_instruction(payload),
                            reason=reason,
                        )

        loop_result = await self._loop_service.run(
            profile=profile_for_loop,
            payload=payload,
            chat_fn=traced_chat_fn,
            tool_fn=tool_fn,
            memory_context=memory_context,
            max_steps=resolve_loop_step_budget(profile, payload),
            on_step=on_step,
            resume_checkpoint=payload.resume_checkpoint,
            native_chat_fn=native_chat_fn if tools_schema else None,
            verify_fn=verify_fn if verify_cmd else None,
            escalation_models=escalation_models,
            max_verify_retries=run_verify_max_retries,
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
        *,
        run_id: str | None = None,
        auto_confirm_risky_tools: bool = False,
        verify_after_patch: bool | None = None,
    ) -> tuple[str, list[tuple[str, str]]]:
        side_effects: list[tuple[str, str]] = []
        self._ensure_tool_allowed(agent_id, tool_name)
        if auto_confirm_risky_tools and tool_name in _RISKY_LOOP_TOOLS:
            arguments = {**arguments, "confirmed": True}
        if tool_name == "describe_tools":
            names = resolve_described_tools(arguments, list(profile.enabled_tools or []))
            return build_tool_schema_response(names), side_effects
        # Множество всех browser-тулов (используется и в allow_online, и в диспатче)
        _browser_tools = {
            "browser_navigate",
            "browser_get_page_state",
            "browser_click",
            "browser_fill",
            "browser_get_text",
            "browser_screenshot",
            "browser_evaluate_js",
            "browser_wait_for",
            "browser_smart_login",
            "browser_smart_search",
            "browser_smart_add_to_cart",
            "browser_allowed_domains",
        }
        if tool_name in ({"web_automation", "web_search"} | _browser_tools) and not profile.allow_online:
            raise AgentOnlineError(f"Agent '{profile.name}' is not configured for online execution.")
        if tool_name == "apply_patch" and self._guardrails is not None:
            content = arguments.get("content")
            if content is not None:
                patch_check = self._guardrails.check_patch_content(str(content))
                if not patch_check.allowed:
                    raise GuardrailBlockedError(patch_check.reason)
        if tool_name in _browser_tools:
            browser = self._playwright_browser
            if browser is None or not browser.available():
                raise AgentOnlineError(
                    "Playwright browser is not available. Set TERMIT_BROWSER_BACKEND=playwright "
                    "and run: pip install playwright && playwright install chromium"
                )
            try:
                if tool_name == "browser_navigate":
                    payload = browser.navigate(
                        str(arguments.get("url", "")),
                        timeout_seconds=int(arguments.get("timeout_seconds", 30)),
                        wait_until=str(arguments.get("wait_until", "domcontentloaded")),
                    )
                elif tool_name == "browser_get_page_state":
                    payload = browser.get_page_state(
                        include_html=bool(arguments.get("include_html", False)),
                        max_elements=int(arguments.get("max_elements", 50)),
                    )
                elif tool_name == "browser_click":
                    payload = browser.click(
                        selector=str(arguments.get("selector", "")),
                        text=str(arguments.get("text", "")),
                        index=arguments.get("index"),
                        confirmed=bool(arguments.get("confirmed", False)),
                    )
                elif tool_name == "browser_fill":
                    payload = browser.fill(
                        selector=str(arguments.get("selector", "")),
                        value=str(arguments.get("value", "")),
                        index=arguments.get("index"),
                        clear_first=bool(arguments.get("clear_first", True)),
                    )
                elif tool_name == "browser_get_text":
                    payload = browser.get_text(
                        selector=str(arguments.get("selector", "")),
                        max_chars=int(arguments.get("max_chars", 10000)),
                    )
                elif tool_name == "browser_screenshot":
                    payload = browser.screenshot(
                        selector=str(arguments.get("selector", "")),
                        full_page=bool(arguments.get("full_page", False)),
                        project_id=str(arguments.get("project_id", "")),
                    )
                elif tool_name == "browser_evaluate_js":
                    payload = browser.evaluate_js(
                        str(arguments.get("expression", "")),
                    )
                elif tool_name == "browser_wait_for":
                    payload = browser.wait_for(
                        selector=str(arguments.get("selector", "")),
                        state=str(arguments.get("state", "visible")),
                        timeout_seconds=int(arguments.get("timeout_seconds", 10)),
                    )
                elif tool_name == "browser_smart_login":
                    payload = browser.smart_login(
                        url=str(arguments.get("url", "")),
                        username=str(arguments.get("username", "")),
                        password=str(arguments.get("password", "")),
                        extra_fields=arguments.get("extra_fields"),
                        submit_text=str(arguments.get("submit_text", "")),
                    )
                elif tool_name == "browser_smart_search":
                    payload = browser.smart_search(
                        query=str(arguments.get("query", "")),
                        url=str(arguments.get("url", "")),
                        max_results=int(arguments.get("max_results", 10)),
                        extract_cards=bool(arguments.get("extract_cards", True)),
                    )
                elif tool_name == "browser_smart_add_to_cart":
                    payload = browser.smart_add_to_cart(
                        product_name=str(arguments.get("product_name", "")),
                        confirmed=bool(arguments.get("confirmed", False)),
                        quantity=arguments.get("quantity"),
                    )
                elif tool_name == "browser_allowed_domains":
                    payload = browser.manage_allowed_domains(
                        add=str(arguments.get("add", "")),
                        remove=str(arguments.get("remove", "")),
                        list_domains=bool(arguments.get("list", False)),
                    )
                # --- Фаза 1: базовые примитивы (7) ---
                elif tool_name == "browser_scroll":
                    payload = browser.scroll(
                        amount=int(arguments.get("amount", 300)),
                        direction=str(arguments.get("direction", "down")),
                        selector=str(arguments.get("selector", "")),
                    )
                elif tool_name == "browser_hover":
                    payload = browser.hover(
                        selector=str(arguments.get("selector", "")),
                    )
                elif tool_name == "browser_double_click":
                    payload = browser.double_click(
                        selector=str(arguments.get("selector", "")),
                    )
                elif tool_name == "browser_right_click":
                    payload = browser.right_click(
                        selector=str(arguments.get("selector", "")),
                    )
                elif tool_name == "browser_type_text":
                    payload = browser.type_text(
                        selector=str(arguments.get("selector", "")),
                        text=str(arguments.get("text", "")),
                        delay=int(arguments.get("delay", 50)),
                    )
                elif tool_name == "browser_press_key":
                    payload = browser.press_key(
                        key=str(arguments.get("key", "")),
                        selector=str(arguments.get("selector", "")),
                    )
                elif tool_name == "browser_drag":
                    payload = browser.drag(
                        source_selector=str(arguments.get("source_selector", "")),
                        target_selector=str(arguments.get("target_selector", "")),
                    )
                # --- Фаза 2: мульти-табы (4) ---
                elif tool_name == "browser_new_tab":
                    payload = browser.new_tab(
                        url=str(arguments.get("url", "")),
                    )
                elif tool_name == "browser_switch_tab":
                    payload = browser.switch_tab(
                        index=int(arguments.get("index", 0)),
                    )
                elif tool_name == "browser_close_tab":
                    payload = browser.close_tab(
                        index=int(arguments.get("index", -1)),
                    )
                elif tool_name == "browser_list_tabs":
                    payload = browser.list_tabs()
                # --- Фаза 3: диалоги, загрузки, хранилище (4) ---
                elif tool_name == "browser_handle_dialog":
                    payload = browser.handle_dialog(
                        action=str(arguments.get("action", "accept")),
                        prompt_text=str(arguments.get("prompt_text", "")),
                    )
                elif tool_name == "browser_upload_file":
                    payload = browser.upload_file(
                        selector=str(arguments.get("selector", "")),
                        file_path=str(arguments.get("file_path", "")),
                    )
                elif tool_name == "browser_cookies":
                    payload = browser.cookies(
                        action=str(arguments.get("action", "get")),
                        cookie_data=arguments.get("cookie_data"),
                    )
                elif tool_name == "browser_local_storage":
                    payload = browser.local_storage(
                        action=str(arguments.get("action", "get")),
                        key=str(arguments.get("key", "")),
                        value=str(arguments.get("value", "")),
                    )
                # --- Фаза 4: визуальный режим (3) ---
                elif tool_name == "browser_screenshot_element":
                    payload = browser.screenshot_element(
                        selector=str(arguments.get("selector", "")),
                    )
                elif tool_name == "browser_element_som":
                    payload = browser.element_som(
                        max_elements=int(arguments.get("max_elements", 30)),
                        selector=str(arguments.get("selector", "")),
                    )
                elif tool_name == "browser_visual_qa":
                    payload = browser.visual_qa(
                        question=str(arguments.get("question", "")),
                        selector=str(arguments.get("selector", "")),
                    )
                # --- Фаза 5: сеть и iframe (3) ---
                elif tool_name == "browser_network_requests":
                    payload = browser.network_requests(
                        action=str(arguments.get("action", "list")),
                        url_filter=str(arguments.get("url_filter", "")),
                    )
                elif tool_name == "browser_iframe_switch":
                    payload = browser.iframe_switch(
                        action=str(arguments.get("action", "list")),
                        selector=str(arguments.get("selector", "")),
                    )
                elif tool_name == "browser_device_emulate":
                    payload = browser.device_emulate(
                        device=str(arguments.get("device", "Desktop")),
                    )
                # --- Фаза 6: смарт-тулы v2 (4) ---
                elif tool_name == "browser_smart_form":
                    payload = browser.smart_form(
                        url=str(arguments.get("url", "")),
                        fields=arguments.get("fields", {}),
                    )
                elif tool_name == "browser_smart_extract":
                    payload = browser.smart_extract(
                        extract_type=str(arguments.get("extract_type", "tables")),
                        selector=str(arguments.get("selector", "")),
                    )
                elif tool_name == "browser_smart_checkout":
                    payload = browser.smart_checkout(
                        url=str(arguments.get("url", "")),
                        steps=arguments.get("steps"),
                        auto_continue=bool(arguments.get("auto_continue", False)),
                    )
                elif tool_name == "browser_smart_captcha_detect":
                    payload = browser.smart_captcha_detect()
                else:
                    payload = {"error": f"Unknown browser tool: {tool_name}"}
            except PlaywrightUnavailableError as exc:
                raise AgentOnlineError(str(exc)) from exc
            side_effects.append((tool_name, str(payload.get("url", payload.get("executed", "")))))
            return json_dumps(payload, ensure_ascii=True), side_effects
        if tool_name == "web_search":
            query = str(arguments.get("query", ""))
            max_results = int(arguments.get("max_results", 5))
            domains_raw = arguments.get("domains")
            domains: list[str] | None = None
            if isinstance(domains_raw, list):
                domains = [str(item) for item in domains_raw if str(item).strip()]
            recency_raw = arguments.get("recency_days")
            recency_days = int(recency_raw) if recency_raw is not None else None
            search_result = self._search.search(
                query,
                max_results=max_results,
                domains=domains,
                recency_days=recency_days,
            )
            side_effects.append(
                ("web_search", f"hits={len(search_result.hits)} citations={len(search_result.citations)}")
            )
            return (
                json.dumps(
                    {
                        "observation": search_result.to_observation(),
                        "citations": search_result.citations,
                        "provider": search_result.provider,
                    },
                    ensure_ascii=True,
                ),
                side_effects,
            )
        if tool_name == "spawn_agent":
            child_agent_id = str(arguments.get("agent_id") or agent_id)
            task = str(arguments.get("task", "")).strip()
            if not task:
                raise ValueError("spawn_agent requires non-empty task.")
            child_payload = AgentRunRequest(
                input=task,
                parent_run_id=run_id,
                use_tool_loop=True,
            )
            child = self.create_run(child_agent_id, child_payload)
            summary = {"run_id": child.run_id, "state": "queued", "parent_run_id": run_id}
            side_effects.append(("spawn_agent", f"child_run_id={child.run_id}"))
            side_effects.append(("spawn_agent_child_event", f"child_run_id={child.run_id} queued"))
            if self._training_signals is not None:
                self._training_signals.try_capture_subagent_run(
                    parent_run_id=run_id or "",
                    child_run_id=child.run_id,
                    task=task,
                    success=False,
                    summary=json.dumps(summary, ensure_ascii=True)[:8000],
                )
            self._append_event(
                run_id=run_id,
                event_type="spawn_agent_child_event",
                state=AgentRunState.running,
                message=f"child_run_id={child.run_id} queued",
                attempt=1,
            )
            return json.dumps(summary, ensure_ascii=True), side_effects
        if tool_name in {
            "generate_image",
            "list_media_assets",
            "vision_qa_media",
            "estimate_media_cost",
            "tts_generate",
            "transcribe_media",
            "compose_media",
            "render_video",
            "wait_media_job",
            "export_gif",
            "export_lottie",
            "run_storyboard",
        }:
            if self._media is None:
                raise AgentPermissionError("Media Studio is not configured.")
            from app.services.media_generation_service import (
                MediaConfirmationRequired,
                MediaStudioError,
            )

            media = self._media
            try:
                if tool_name == "generate_image":
                    result = media.generate_image(
                        prompt=str(arguments.get("prompt", "")),
                        width=int(arguments.get("width", 1024)),
                        height=int(arguments.get("height", 1024)),
                        project_id=str(arguments.get("project_id", "default")),
                        run_id=run_id,
                        scene_id=str(arguments.get("scene_id", "")) or None,
                        provider=str(arguments.get("provider", "")) or None,
                        confirmed=bool(arguments.get("confirmed", False)),
                        output_name=str(arguments.get("output_path", "")) or None,
                    )
                    payload_out = result.to_observation()
                    side_effects.append(("generate_image", result.asset.asset_id))
                    return json.dumps(payload_out, ensure_ascii=True), side_effects
                if tool_name == "list_media_assets":
                    items = media.list_assets(
                        project_id=str(arguments.get("project_id", "")) or None,
                        run_id=str(arguments.get("run_id", "")) or run_id,
                        scene_id=str(arguments.get("scene_id", "")) or None,
                        limit=int(arguments.get("limit", 50)),
                    )
                    payload_out = {"assets": [item.to_dict() for item in items]}
                    return json.dumps(payload_out, ensure_ascii=True), side_effects
                if tool_name == "vision_qa_media":
                    qa = media.vision_qa_media(
                        asset_id=str(arguments.get("asset_id", "")),
                        criteria=str(arguments.get("criteria", "")),
                        min_score=float(arguments.get("min_score", 0.75)),
                    )
                    return json.dumps(qa.to_observation(), ensure_ascii=True), side_effects
                if tool_name == "estimate_media_cost":
                    storyboard_path = str(arguments.get("storyboard_path", "")).strip()
                    storyboard_raw = arguments.get("storyboard")
                    if isinstance(storyboard_raw, dict):
                        estimate = media.estimate_cost(storyboard=storyboard_raw)
                    elif storyboard_path:
                        estimate = media.estimate_cost(storyboard_path=storyboard_path)
                    else:
                        raise MediaStudioError(
                            "estimate_media_cost requires storyboard_path or storyboard object."
                        )
                    return json.dumps(estimate.to_dict(), ensure_ascii=True), side_effects
                if tool_name == "tts_generate":
                    tts = media.tts_generate(
                        text=str(arguments.get("text", "")),
                        project_id=str(arguments.get("project_id", "default")),
                        run_id=run_id,
                        voice_id=str(arguments.get("voice_id", "")) or None,
                        language=str(arguments.get("language", "ru")),
                        confirmed=bool(arguments.get("confirmed", False)),
                        provider=str(arguments.get("provider", "")) or None,
                    )
                    side_effects.append(("tts_generate", tts.asset.asset_id))
                    return json.dumps(tts.to_observation(), ensure_ascii=True), side_effects
                if tool_name == "transcribe_media":
                    tr = media.transcribe_media(
                        asset_id=str(arguments.get("asset_id", "")),
                        project_id=str(arguments.get("project_id", "default")),
                        run_id=run_id,
                        language=str(arguments.get("language", "")) or None,
                    )
                    side_effects.append(("transcribe_media", tr.asset.asset_id))
                    return json.dumps(tr.to_observation(), ensure_ascii=True), side_effects
                if tool_name == "compose_media":
                    timeline_raw = arguments.get("timeline")
                    timeline = timeline_raw if isinstance(timeline_raw, dict) else None
                    composed = media.compose_media(
                        project_id=str(arguments.get("project_id", "default")),
                        run_id=run_id,
                        timeline_path=str(arguments.get("timeline_path", "")).strip() or None,
                        timeline=timeline,
                        output_name=str(arguments.get("output_name", "")) or None,
                        preset=str(arguments.get("preset", "youtube_16x9")),
                    )
                    side_effects.append(("compose_media", composed.asset.asset_id))
                    return json.dumps(composed.to_observation(), ensure_ascii=True), side_effects
                if tool_name == "render_video":
                    job = media.render_video(
                        prompt=str(arguments.get("prompt", "")),
                        project_id=str(arguments.get("project_id", "default")),
                        run_id=run_id,
                        scene_id=str(arguments.get("scene_id", "")) or None,
                        source_asset_id=str(arguments.get("source_asset_id", "")) or None,
                        mode=str(arguments.get("mode", "image_to_video")),
                        duration_sec=float(arguments.get("duration_sec", 5)),
                        provider=str(arguments.get("provider", "")) or None,
                        confirmed=bool(arguments.get("confirmed", False)),
                    )
                    side_effects.append(("render_video", job.job_id))
                    return json.dumps(job.to_dict(), ensure_ascii=True), side_effects
                if tool_name == "wait_media_job":
                    job = media.wait_media_job(
                        job_id=str(arguments.get("job_id", "")),
                        timeout_sec=int(arguments.get("timeout_sec", 600)),
                    )
                    return json.dumps(job.to_dict(), ensure_ascii=True), side_effects
                if tool_name == "export_gif":
                    raw_ids = arguments.get("asset_ids", [])
                    asset_ids = [str(x) for x in raw_ids] if isinstance(raw_ids, list) else []
                    gif_asset = media.export_gif(
                        asset_ids=asset_ids,
                        project_id=str(arguments.get("project_id", "default")),
                        run_id=run_id,
                        fps=int(arguments.get("fps", 8)),
                        width=int(arguments.get("width", 480)),
                    )
                    return json.dumps(gif_asset.to_dict(), ensure_ascii=True), side_effects
                if tool_name == "export_lottie":
                    raw_ids = arguments.get("asset_ids", [])
                    asset_ids = [str(x) for x in raw_ids] if isinstance(raw_ids, list) else []
                    lottie_asset = media.export_lottie(
                        asset_ids=asset_ids,
                        project_id=str(arguments.get("project_id", "default")),
                        run_id=run_id,
                        fps=int(arguments.get("fps", 8)),
                        width=int(arguments.get("width", 480)),
                    )
                    return json.dumps(lottie_asset.to_dict(), ensure_ascii=True), side_effects
                if tool_name == "run_storyboard":
                    sb_raw = arguments.get("storyboard")
                    storyboard = sb_raw if isinstance(sb_raw, dict) else None
                    master = media.run_storyboard(
                        storyboard_path=str(arguments.get("storyboard_path", "")).strip() or None,
                        storyboard=storyboard,
                        project_id=str(arguments.get("project_id", "default")),
                        run_id=run_id,
                        brand_kit_id=str(arguments.get("brand_kit_id", "")) or None,
                        max_scenes=int(arguments.get("max_scenes", 6)),
                        confirmed=bool(arguments.get("confirmed", False)),
                    )
                    side_effects.append(("run_storyboard", master.asset.asset_id))
                    return json.dumps(master.to_observation(), ensure_ascii=True), side_effects
            except MediaConfirmationRequired as exc:
                return (
                    json.dumps(
                        {
                            "requires_confirmation": True,
                            "message": str(exc),
                            "tool": tool_name,
                            "hint": "Re-call with confirmed=true after user approval.",
                        },
                        ensure_ascii=True,
                    ),
                    side_effects,
                )
            except MediaStudioError as exc:
                raise AgentPermissionError(str(exc)) from exc
            raise AgentPermissionError(f"Unsupported media tool: {tool_name}")
        if tool_name == "mcp_invoke":
            if self._mcp is None:
                raise AgentPermissionError("MCP registry is not configured.")
            server_id = str(arguments.get("server_id", ""))
            mcp_tool = str(arguments.get("tool_name", ""))
            mcp_args = arguments.get("arguments", {})
            if not isinstance(mcp_args, dict):
                mcp_args = {}
            self._ensure_mcp_tool_allowed(profile, server_id, mcp_tool)
            result_json = self._mcp.invoke_tool(server_id, mcp_tool, mcp_args)
            side_effects.append(("mcp_invoke", f"server={server_id} tool={mcp_tool}"))
            return result_json, side_effects
        if tool_name == "mcp_read_resource":
            if self._mcp is None:
                raise AgentPermissionError("MCP registry is not configured.")
            server_id = str(arguments.get("server_id", ""))
            uri = str(arguments.get("uri", ""))
            if not server_id or not uri:
                raise AgentPermissionError("mcp_read_resource requires server_id and uri.")
            self._ensure_mcp_server_allowed(profile, server_id)
            payload = self._mcp.read_resource(server_id, uri)
            from app.services.mcp_context_service import McpContextService

            result_json = McpContextService.serialize_read_result(payload)
            side_effects.append(("mcp_read_resource", f"server={server_id} uri={uri}"))
            return result_json, side_effects
        if tool_name == "mcp_get_prompt":
            if self._mcp is None:
                raise AgentPermissionError("MCP registry is not configured.")
            server_id = str(arguments.get("server_id", ""))
            prompt_name = str(arguments.get("name", ""))
            prompt_args = arguments.get("arguments", {})
            if not isinstance(prompt_args, dict):
                prompt_args = {}
            if not server_id or not prompt_name:
                raise AgentPermissionError("mcp_get_prompt requires server_id and name.")
            self._ensure_mcp_server_allowed(profile, server_id)
            payload = self._mcp.get_prompt(server_id, prompt_name, prompt_args)
            from app.services.mcp_context_service import McpContextService

            result_json = McpContextService.serialize_prompt_result(payload)
            side_effects.append(("mcp_get_prompt", f"server={server_id} name={prompt_name}"))
            return result_json, side_effects
        if tool_name == "invoke_skill":
            if self._skills is None:
                raise AgentPermissionError("Skill store is not configured.")
            skill_id = str(arguments.get("skill_id", "")).strip()
            if not skill_id:
                raise AgentPermissionError("invoke_skill requires skill_id.")
            skill = self._skills.get_skill(skill_id)
            if skill is None:
                return (
                    json.dumps(
                        {
                            "ok": False,
                            "skill_id": skill_id,
                            "error": f"Skill not found: {skill_id}",
                            "available": [
                                {"skill_id": item.skill_id, "name": item.name, "description": item.description}
                                for item in self._skills.list_skills()
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    side_effects,
                )
            body = self._skills.skill_body(skill)
            side_effects.append(("invoke_skill", skill_id))
            return (
                json.dumps(
                    {
                        "ok": True,
                        "skill_id": skill.skill_id,
                        "name": skill.name,
                        "description": skill.description,
                        "path": skill.path,
                        "content": body,
                    },
                    ensure_ascii=False,
                ),
                side_effects,
            )
        built = build_tool_arguments(tool_name, arguments)
        ssh_cfg = _active_ssh_config.get()
        if tool_name == "list_files":
            result = (
                self._ssh.list_files(ssh_cfg, built)
                if ssh_cfg is not None
                else self._tooling.list_files(built)
            )
        elif tool_name == "read_file":
            result = (
                self._ssh.read_file(ssh_cfg, built)
                if ssh_cfg is not None
                else self._tooling.read_file(built)
            )
        elif tool_name == "execute_command":
            result = (
                self._ssh.execute_command(ssh_cfg, built)
                if ssh_cfg is not None
                else self._tooling.execute_command(built)
            )
        elif tool_name == "apply_patch":
            result = (
                self._ssh.apply_patch(ssh_cfg, built)
                if ssh_cfg is not None
                else self._tooling.apply_patch(built)
            )
            effective_verify = (
                verify_after_patch if verify_after_patch is not None else self._verify_after_patch
            )
            verify_cmd = (
                resolve_verify_command(str(self._tooling.root), self._verify_cmd)
                if effective_verify
                else ""
            )
            if result.applied and verify_cmd:
                if ssh_cfg is not None:
                    verify_result = self._ssh.execute_command(
                        ssh_cfg,
                        ExecuteCommandRequest(
                            command=verify_cmd,
                            path=".",
                            dry_run=False,
                            confirmed=True,
                        ),
                    )
                else:
                    verify_result = self._tooling.execute_command(
                        ExecuteCommandRequest(
                            command=verify_cmd,
                            path=".",
                            dry_run=False,
                            confirmed=True,
                        )
                    )
                verify_msg = (
                    f"Verify after patch: exit_code={verify_result.exit_code}, "
                    f"executed={verify_result.executed}, "
                    f"stdout={(verify_result.stdout or verify_result.stderr)[:300]}"
                )
                event_type = "patch_verify"
                if verify_result.executed and verify_result.exit_code != 0:
                    event_type = "patch_verify_failed"
                side_effects.append((event_type, verify_msg))
                return (
                    json.dumps(
                        {
                            "patch": result.model_dump(mode="json"),
                            "verify": verify_result.model_dump(mode="json"),
                            "verify_failed": bool(
                                verify_result.executed and verify_result.exit_code != 0
                            ),
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

    def _emit_run_hook(
        self,
        *,
        event_type: str,
        run_id: str,
        agent_id: str,
        state: str,
        message: str = "",
    ) -> None:
        if self._hooks is None:
            return
        self._hooks.emit(
            HookEvent(
                event_type=event_type,
                run_id=run_id,
                agent_id=agent_id,
                state=state,
                message=message,
            )
        )

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

    @staticmethod
    def _ensure_mcp_server_allowed(profile: AgentProfileResponse, server_id: str) -> None:
        allowed_servers = [item.strip() for item in profile.allowed_mcp_servers if item.strip()]
        if allowed_servers and "*" not in allowed_servers and server_id not in set(allowed_servers):
            raise AgentPermissionError(
                f"MCP server '{server_id}' is not allowed for agent '{profile.name}'."
            )

    @staticmethod
    def _ensure_mcp_tool_allowed(
        profile: AgentProfileResponse,
        server_id: str,
        tool_name: str,
    ) -> None:
        allowed_servers = [item.strip() for item in profile.allowed_mcp_servers if item.strip()]
        if allowed_servers and "*" not in allowed_servers and server_id not in set(allowed_servers):
            raise AgentPermissionError(
                f"MCP server '{server_id}' is not allowed for agent '{profile.name}'."
            )
        allowed_tools = [item.strip() for item in profile.allowed_mcp_tools if item.strip()]
        if allowed_tools and "*" not in allowed_tools and tool_name not in set(allowed_tools):
            raise AgentPermissionError(
                f"MCP tool '{tool_name}' is not allowed for agent '{profile.name}'."
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

    def _run_async_with_guard(self, coro, timeout_seconds: int):
        """Выполнить async-корутину в daemon-потоке с защитой от зависания.

        Проблема: asyncio.wait_for не может прервать корутину, если она
        заблокирована на GIL (SSL handshake, синхронный I/O). Вынос asyncio.run()
        в отдельный daemon-поток позволяет worker'у продолжить работу даже при
        зависшем HTTP-запросе. Orphan-поток остаётся до перезапуска процесса,
        но cleanup_stale_active_runs подчистит orphan-ран.
        """
        result_holder: list = []
        error_holder: list[Exception] = []

        def _target() -> None:
            try:
                result_holder.append(asyncio.run(coro))
            except Exception as exc:
                error_holder.append(exc)

        thread = Thread(target=_target, daemon=True, name=f"run-async-{uuid4().hex[:8]}")
        thread.start()
        # join с запасом +10s на штатное завершение после wait_for-timeout
        thread.join(timeout=timeout_seconds + 10)

        if thread.is_alive():
            # Поток завис — worker не блокируется, orphan-поток остаётся
            raise TimeoutError(
                f"Worker guard: run exceeded {timeout_seconds}s "
                f"(SSL/GIL hang suspected). Thread leaked — cleanup will "
                f"detect orphan run."
            )

        if error_holder:
            raise error_holder[0]

        return result_holder[0]

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
        active_payload = payload
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
                current = self._run_store.get_run(run_id)
                if current is not None:
                    self._publish_run(current)

            try:
                profile = self.get_agent(agent_id)
                coro = asyncio.wait_for(
                    self._run_with_profile(profile, active_payload, run_id=run_id, attempt=attempt),
                    timeout=self._run_timeout_seconds,
                )
                result = self._run_async_with_guard(coro, self._run_timeout_seconds)
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
                    current.outcome_class = self._resolve_outcome_class(current, run_id)
                    self._run_store.put_run(current)
                    self._append_event(
                        run_id=run_id,
                        event_type="run_completed",
                        state=AgentRunState.completed,
                        message="Run completed successfully.",
                        attempt=attempt,
                    )
                    completion_events = self._run_store.get_events(run_id, limit=500)
                    summary_payload = activity_summary_from_events(completion_events, in_progress=False)
                    if summary_payload.get("files_count", 0) > 0:
                        self._append_event(
                            run_id=run_id,
                            event_type="activity_summary",
                            state=AgentRunState.completed,
                            message=summary_payload["label"],
                            attempt=attempt,
                            payload=summary_payload,
                        )
                    self._emit_run_hook(
                        event_type="run.stop",
                        run_id=run_id,
                        agent_id=agent_id,
                        state=AgentRunState.completed.value,
                        message="Run completed successfully.",
                    )
                    if profile.use_long_term_memory and self._agent_memory is not None:
                        self._agent_memory.append(
                            agent_id=agent_id,
                            outcome="completed",
                            summary=payload.input[:120],
                            detail=current.response[:500],
                            run_id=run_id,
                            workspace_scope=payload.workspace_scope or payload.retrieval_path_prefix,
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
                            instruction=self._capture_instruction(payload),
                            response=current.response,
                            session_id=current.session_id,
                            trajectory=trajectory,
                        )
                    self._publish_run(current)
                return
            except AgentAwaitingConfirmation as exc:
                with self._lock:
                    current = self._run_store.get_run(run_id)
                    if current is None:
                        return
                    current.state = AgentRunState.awaiting_confirmation
                    current.updated_at = _utc_now_iso()
                    current.checkpoint_json = json_dumps(exc.checkpoint, ensure_ascii=True)
                    current.error = None
                    self._run_store.put_run(current)
                    self._append_event(
                        run_id=run_id,
                        event_type="confirmation_required",
                        state=AgentRunState.awaiting_confirmation,
                        message="Risky tool requires user confirmation.",
                        attempt=attempt,
                    )
                    current = self._run_store.get_run(run_id)
                    if current is not None:
                        self._publish_run(current)
                return
            except AgentLoopError as exc:
                if exc.checkpoint:
                    with self._lock:
                        current = self._run_store.get_run(run_id)
                        if current is None:
                            return
                        current.checkpoint_json = json_dumps(exc.checkpoint, ensure_ascii=True)
                        current.updated_at = _utc_now_iso()
                        self._run_store.put_run(current)
                failure_class = self._classify_failure(exc)
                is_last = attempt >= self._run_max_attempts
                with self._lock:
                    current = self._run_store.get_run(run_id)
                    if current is None:
                        return
                    current.updated_at = _utc_now_iso()
                    current.error = str(exc)
                    current.failure_class = failure_class
                    current.outcome_class = self._resolve_outcome_class(current, run_id)
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
                        self._emit_run_hook(
                            event_type="run.failed",
                            run_id=run_id,
                            agent_id=agent_id,
                            state=AgentRunState.failed.value,
                            message=str(exc),
                        )
                        self._publish_run(current)
                        return

                    self._run_store.put_run(current)
                    self._append_event(
                        run_id=run_id,
                        event_type="run_retry_scheduled",
                        state=AgentRunState.running,
                        message=f"Attempt {attempt} failed ({failure_class}). Scheduling retry.",
                        attempt=attempt,
                    )
                    fallback_payload = self._apply_policy_fallback(active_payload, failure_class)
                    if fallback_payload.model_dump() != active_payload.model_dump():
                        active_payload = fallback_payload
                        self._append_event(
                            run_id=run_id,
                            event_type="policy_fallback_applied",
                            state=AgentRunState.running,
                            message=(
                                "Applied constrained plan + safe-exec fallback "
                                f"(run_mode={active_payload.run_mode}, "
                                f"policy_preset={active_payload.policy_preset or 'default'})."
                            ),
                            attempt=attempt + 1,
                        )
                if self._run_retry_backoff_ms > 0:
                    time.sleep((self._run_retry_backoff_ms * (2 ** (attempt - 1))) / 1000.0)
                continue
            except TimeoutError:
                failure_class = "run_timeout"
                is_last = attempt >= self._run_max_attempts
                with self._lock:
                    current = self._run_store.get_run(run_id)
                    if current is None:
                        return
                    current.updated_at = _utc_now_iso()
                    current.error = (
                        f"Run exceeded timeout ({self._run_timeout_seconds}s). "
                        "Task was interrupted to keep workers healthy."
                    )
                    current.failure_class = failure_class
                    current.outcome_class = self._resolve_outcome_class(current, run_id)
                    if is_last:
                        current.state = AgentRunState.failed
                        self._run_store.put_run(current)
                        self._append_event(
                            run_id=run_id,
                            event_type="run_dead_lettered",
                            state=AgentRunState.failed,
                            message=(
                                f"Run failed after {self._run_max_attempts} attempts: "
                                f"{failure_class}: timeout={self._run_timeout_seconds}s"
                            ),
                            attempt=attempt,
                        )
                        self._emit_run_hook(
                            event_type="run.failed",
                            run_id=run_id,
                            agent_id=agent_id,
                            state=AgentRunState.failed.value,
                            message=current.error,
                        )
                        self._publish_run(current)
                        return

                    self._run_store.put_run(current)
                    self._append_event(
                        run_id=run_id,
                        event_type="run_retry_scheduled",
                        state=AgentRunState.running,
                        message=(
                            f"Attempt {attempt} failed ({failure_class}). "
                            f"Scheduling retry after timeout={self._run_timeout_seconds}s."
                        ),
                        attempt=attempt,
                    )
                if self._run_retry_backoff_ms > 0:
                    time.sleep((self._run_retry_backoff_ms * (2 ** (attempt - 1))) / 1000.0)
                continue
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
                    current.outcome_class = self._resolve_outcome_class(current, run_id)
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
                        self._emit_run_hook(
                            event_type="run.failed",
                            run_id=run_id,
                            agent_id=agent_id,
                            state=AgentRunState.failed.value,
                            message=str(exc),
                        )
                        self._publish_run(current)
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
    def _apply_policy_fallback(payload: AgentRunRequest, failure_class: str) -> AgentRunRequest:
        """Switch degraded retries to constrained plan + safe tool policy."""
        if failure_class not in _POLICY_FALLBACK_FAILURE_CLASSES:
            return payload
        updates: dict[str, object] = {
            "auto_confirm_risky_tools": False,
        }
        if (payload.run_mode or "agent").strip().lower() == "agent":
            updates["run_mode"] = "plan"
        preset = (payload.policy_preset or "").strip()
        if preset in {"", "autopilot", "team"}:
            updates["policy_preset"] = "strict"
        if _POLICY_FALLBACK_HINT not in payload.input:
            updates["input"] = payload.input + _POLICY_FALLBACK_HINT
        return payload.model_copy(update=updates)

    @staticmethod
    def _classify_failure(exc: Exception) -> str:
        if isinstance(exc, AgentLoopError):
            return exc.failure_class or "loop_error"
        if isinstance(exc, AgentOnlineError):
            return "online_error"
        if isinstance(exc, AgentPermissionError):
            return "permission_error"
        if isinstance(exc, AgentNotFoundError):
            return "agent_not_found"
        if isinstance(exc, TimeoutError):
            return "run_timeout"
        return "execution_error"

    def _resolve_outcome_class(self, run: AgentRunRecordResponse, run_id: str) -> str:
        events = [
            {"message": event.message, "event_type": event.event_type}
            for event in self._run_store.get_events(run_id, limit=80)
        ]
        return classify_agent_outcome(
            state=run.state.value,
            failure_class=run.failure_class,
            response=run.response,
            error=run.error,
            events=events,
        )

    @staticmethod
    def _safe_run_age_seconds(updated_at_iso: str, now_ts: float) -> float:
        try:
            updated = datetime.fromisoformat(updated_at_iso).timestamp()
        except ValueError:
            return 0.0
        return max(0.0, now_ts - updated)

    def _publish_run(self, record: AgentRunRecordResponse) -> None:
        payload = record.model_dump(mode="json")
        if record.state in {
            AgentRunState.completed,
            AgentRunState.failed,
            AgentRunState.cancelled,
            AgentRunState.awaiting_confirmation,
        }:
            payload["terminal"] = True
        self._notifier.publish(record.run_id, "status", payload)

    def _append_event(
        self,
        *,
        run_id: str,
        event_type: str,
        state: AgentRunState,
        message: str,
        attempt: int,
        payload: dict[str, object] | None = None,
    ) -> None:
        event = AgentRunEvent(
            event_type=event_type,
            state=state,
            message=message,
            timestamp=_utc_now_iso(),
            attempt=attempt,
            payload=payload,
        )
        self._run_store.append_event(run_id=run_id, event=event)
        self._run_store.trim_events(run_id=run_id, max_events=self._max_events_per_run)
        self._notifier.publish(run_id, "timeline", event.model_dump(mode="json"))
        self._append_parent_timeline_event(run_id, event)

    def _append_parent_timeline_event(self, run_id: str, event: AgentRunEvent) -> None:
        run = self._run_store.get_run(run_id)
        if run is None or not run.parent_run_id:
            return
        parent = self._run_store.get_run(run.parent_run_id)
        if parent is None:
            return
        child_event = AgentRunEvent(
            event_type="child_run_timeline",
            state=parent.state,
            message=f"{run.run_id} · {event.event_type} · {event.message}",
            timestamp=event.timestamp,
            attempt=event.attempt,
            payload=event.payload,
        )
        self._run_store.append_event(parent.run_id, child_event)
        self._run_store.trim_events(parent.run_id, max_events=self._max_events_per_run)
        self._notifier.publish(parent.run_id, "timeline", child_event.model_dump(mode="json"))

    @staticmethod
    def _extract_patch_path(observation: str) -> str:
        try:
            data = json.loads(observation)
        except json.JSONDecodeError:
            return ""
        if not isinstance(data, dict):
            return ""
        patch = data.get("patch")
        if isinstance(patch, dict):
            return str(patch.get("path", "")).strip()
        return str(data.get("path", "")).strip()

    @staticmethod
    def _patch_was_applied(observation: str) -> bool:
        try:
            data = json.loads(observation)
        except json.JSONDecodeError:
            return False
        if not isinstance(data, dict):
            return False
        patch = data.get("patch")
        if isinstance(patch, dict):
            return bool(patch.get("applied"))
        return bool(data.get("applied"))

    def _truncate_response(self, text: str) -> str:
        if len(text) <= self._max_response_chars:
            return text
        marker = "\n\n[response truncated by retention policy]"
        safe = max(0, self._max_response_chars - len(marker))
        return text[:safe] + marker
