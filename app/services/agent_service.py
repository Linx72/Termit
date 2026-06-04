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
from app.services.agent_run_notifier import AgentRunNotifier
from app.services.build_workflow_service import BuildWorkflowService
from app.services.ssh_workspace_service import SshWorkspaceConfig, SshWorkspaceService
from app.services.browser_workflow_service import BrowserWorkflowService
from app.services.playwright_browser_service import PlaywrightBrowserService, PlaywrightUnavailableError
from app.services.chat_service import ChatService
from app.services.context_enrichment_service import ContextEnrichmentService
from app.services.guardrail_service import GuardrailService
from app.services.mcp_registry_service import McpRegistryService
from app.services.search_provider import SearchProvider, StubSearchProvider
from app.services.skill_store import SkillStore
from app.services.skill_selector_service import SkillSelectorService, SkillSelectionResult
from app.services.tooling_service import ToolingService
from app.services.trace_span_store import TraceSpanStore
from app.services.training_signal_store import TrainingSignalStore
from app.services.patch_outcome_store import PatchOutcomeStore
from app.services.agent_tool_schema import build_openai_tools
from app.services.loop_step_budget import resolve_loop_step_budget
from app.services.repo_profile_resolver import infer_repo_profile_id
from app.services.verify_command_resolver import resolve_verify_command


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
        max_events_per_run: int = 500,
        max_response_chars: int = 12000,
        retention_days: int = 14,
        training_signal_store: Optional[TrainingSignalStore] = None,
        patch_outcome_store: Optional[PatchOutcomeStore] = None,
        verify_after_patch: bool = False,
        verify_cmd: str = "",
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
        self._max_events_per_run = max(1, max_events_per_run)
        self._max_response_chars = max(256, max_response_chars)
        self._retention_days = max(1, retention_days)
        self._training_signals = training_signal_store
        self._patch_outcomes = patch_outcome_store
        self._verify_after_patch = verify_after_patch
        self._verify_cmd = verify_cmd.strip()
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
        self._ssh = SshWorkspaceService(tooling)
        self._notifier = AgentRunNotifier.get()
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
        metrics: dict[str, object] = {
            "queue_size": queue_size,
            "queue_capacity": self._queue_capacity,
            "queue_utilization_percent": utilization,
            "worker_count": self._worker_count,
            "alive_workers": alive_workers,
            "total_runs": total_runs,
            "by_state": by_state,
            "active_runs": active_runs,
        }
        metrics.update(self._run_store.tool_loop_event_metrics())
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
            record.checkpoint_json = json.dumps(checkpoint, ensure_ascii=True)
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
        if skill_selection is not None and skill_selection.selected_skill_ids:
            profile_with_skills = self._append_skill_block(profile, skill_selection.selected_skill_ids)
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
    ) -> AgentProfileResponse:
        if not skill_ids or self._skills is None:
            return profile
        skill_block = self._skills.build_prompt_block(skill_ids)
        if not skill_block:
            return profile
        return profile.model_copy(update={"system_prompt": f"{profile.system_prompt}\n\n{skill_block}"})

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
            memory_context = self._agent_memory.get_context(
                profile.agent_id,
                workspace_scope=scope,
            )

        resolved_model, escalation_models = self._resolve_run_model(profile, payload)
        profile_for_loop = profile.model_copy(update={"model": resolved_model})

        skill_selection = self._resolve_mounted_skills(profile, payload)
        if skill_selection is not None and skill_selection.selected_skill_ids:
            profile_for_loop = self._append_skill_block(profile_for_loop, skill_selection.selected_skill_ids)
            if run_id:
                self._append_event(
                    run_id=run_id,
                    event_type="skills_mounted",
                    state=AgentRunState.running,
                    message=json.dumps(
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
            enrichment_lines = self._context_enrichment.build_agent_context_lines(payload, profile)
            if enrichment_lines:
                memory_context = enrichment_lines + memory_context

        tools_schema = build_openai_tools(list(profile.enabled_tools))
        run_verify_after_patch = (
            payload.verify_after_patch
            if payload.verify_after_patch is not None
            else self._verify_after_patch
        )
        run_auto_confirm = (
            payload.auto_confirm_risky_tools
            if payload.auto_confirm_risky_tools is not None
            else self._auto_confirm_risky_tools
        )
        configured_verify = self._verify_cmd if run_verify_after_patch else ""
        verify_cmd = resolve_verify_command(str(self._tooling.root), configured_verify)

        def verify_fn() -> tuple[bool, str]:
            if not verify_cmd:
                return True, "Verify skipped: no command configured."
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
            return ok, f"exit_code={result.exit_code}; {detail}"

        async def native_chat_fn(request: ChatRequest):
            return await self._chat_service.chat_with_tools(request, tools_schema)

        def tool_fn(tool_name: str, arguments: dict[str, object]) -> str:
            started = time.perf_counter()
            try:
                observation, side_effects = self._invoke_loop_tool(
                    profile.agent_id,
                    profile,
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
                        extra={"tool_name": tool_name, "arguments": arguments},
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
            else:
                event_type = "tool_loop_step"
            self._append_event(
                run_id=run_id,
                event_type=event_type,
                state=AgentRunState.running,
                message=message,
                attempt=attempt,
            )
            trace_payload = json.dumps(
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
                            instruction=payload.input,
                            chosen_patch=chosen_patch,
                        )
                    if verified:
                        self._training_signals.try_capture_tool_step(
                            run_id=run_id,
                            step=step.step,
                            action=step.action,
                            tool=step.tool,
                            observation=obs_text,
                            instruction=payload.input,
                            verified=True,
                        )
                elif step.action == "tool" and step.tool == "execute_command" and verified:
                    self._training_signals.try_capture_tool_step(
                        run_id=run_id,
                        step=step.step,
                        action=step.action,
                        tool=step.tool,
                        observation=obs_text,
                        instruction=payload.input,
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
                            instruction=payload.input,
                            reason=reason,
                        )

        loop_result = await self._loop_service.run(
            profile=profile_for_loop,
            payload=payload,
            chat_fn=self._chat_service.chat,
            tool_fn=tool_fn,
            memory_context=memory_context,
            max_steps=resolve_loop_step_budget(profile, payload),
            on_step=on_step,
            resume_checkpoint=payload.resume_checkpoint,
            native_chat_fn=native_chat_fn if tools_schema else None,
            verify_fn=verify_fn if verify_cmd else None,
            escalation_models=escalation_models,
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
        if tool_name in {
            "web_automation",
            "web_search",
            "browser_navigate",
            "browser_snapshot",
            "browser_click",
        } and not profile.allow_online:
            raise AgentOnlineError(f"Agent '{profile.name}' is not configured for online execution.")
        if tool_name == "apply_patch" and self._guardrails is not None:
            content = arguments.get("content")
            if content is not None:
                patch_check = self._guardrails.check_patch_content(str(content))
                if not patch_check.allowed:
                    raise GuardrailBlockedError(patch_check.reason)
        if tool_name in {"browser_navigate", "browser_snapshot", "browser_click"}:
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
                    )
                elif tool_name == "browser_snapshot":
                    payload = browser.snapshot()
                else:
                    payload = browser.click(
                        str(arguments.get("selector", "")),
                        confirmed=bool(arguments.get("confirmed", False)),
                    )
            except PlaywrightUnavailableError as exc:
                raise AgentOnlineError(str(exc)) from exc
            side_effects.append((tool_name, str(payload.get("url", payload.get("executed", "")))))
            return json.dumps(payload, ensure_ascii=True), side_effects
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
                use_tool_loop=False,
            )
            child = self.create_run(child_agent_id, child_payload)
            summary = self._wait_for_run(child.run_id, timeout_seconds=120)
            side_effects.append(("spawn_agent", f"child_run_id={child.run_id}"))
            if self._training_signals is not None:
                child_state = str(summary.get("state", "")) if isinstance(summary, dict) else ""
                self._training_signals.try_capture_subagent_run(
                    parent_run_id=run_id or "",
                    child_run_id=child.run_id,
                    task=task,
                    success=child_state == AgentRunState.completed.value,
                    summary=json.dumps(summary, ensure_ascii=True)[:8000],
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
            result_json = self._mcp.invoke_tool(server_id, mcp_tool, mcp_args)
            side_effects.append(("mcp_invoke", f"server={server_id} tool={mcp_tool}"))
            return result_json, side_effects
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
            verify_cmd = resolve_verify_command(
                str(self._tooling.root),
                self._verify_cmd if effective_verify else "",
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

    def _wait_for_run(self, run_id: str, *, timeout_seconds: int = 120) -> dict[str, object]:
        deadline = time.time() + max(5, timeout_seconds)
        while time.time() < deadline:
            record = self._run_store.get_run(run_id)
            if record is None:
                return {"run_id": run_id, "state": "missing"}
            if record.state in {
                AgentRunState.completed,
                AgentRunState.failed,
                AgentRunState.cancelled,
            }:
                return {
                    "run_id": run_id,
                    "state": record.state.value,
                    "response": record.response[:2000],
                    "error": record.error,
                }
            time.sleep(0.5)
        return {"run_id": run_id, "state": "timeout"}

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
                current = self._run_store.get_run(run_id)
                if current is not None:
                    self._publish_run(current)

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
                            instruction=payload.input,
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
                    current.checkpoint_json = json.dumps(exc.checkpoint, ensure_ascii=True)
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
                        current.checkpoint_json = json.dumps(exc.checkpoint, ensure_ascii=True)
                        current.updated_at = _utc_now_iso()
                        self._run_store.put_run(current)
                raise
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
    ) -> None:
        event = AgentRunEvent(
            event_type=event_type,
            state=state,
            message=message,
            timestamp=_utc_now_iso(),
            attempt=attempt,
        )
        self._run_store.append_event(run_id=run_id, event=event)
        self._run_store.trim_events(run_id=run_id, max_events=self._max_events_per_run)
        self._notifier.publish(run_id, "timeline", event.model_dump(mode="json"))

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
