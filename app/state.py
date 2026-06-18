from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import time
from typing import Optional

from app.core.config import get_settings
from app.services.agent_registry_store import AgentRegistryStore
from app.services.agent_service import AgentService
from app.services.agent_run_store import InMemoryAgentRunStore
from app.services.agent_hook_service import AgentHookService
from app.services.agent_maintenance_scheduler_service import AgentMaintenanceSchedulerService
from app.services.agent_schedule_service import AgentScheduleService
from app.services.guardrail_service import GuardrailService
from app.services.mcp_registry_service import McpRegistryService
from app.services.search_provider import build_search_provider
from app.services.skill_store import SkillStore
from app.services.skill_selector_service import SkillSelectorService
from app.services.trace_span_store import TraceSpanStore
from app.services.agent_memory_store import AgentMemoryStore
from app.services.agent_eval_service import AgentEvalService
from app.services.agent_loop_service import AgentLoopService
from app.services.local_runtime_service import LocalRuntimeService
from app.services.chat_service import ChatService
from app.services.context_compaction import ContextCompactor
from app.services.code_retrieval_service import CodeRetrievalService
from app.services.agent_templates_store import AgentTemplatesStore
from app.services.context_enrichment_service import ContextEnrichmentService
from app.services.context_packing_service import ContextPackingService
from app.services.project_rules_store import ProjectRulesStore
from app.services.repo_map_service import RepoMapService
from app.services.symbol_index_service import SymbolIndexService
from app.services.browser_workflow_service import BrowserWorkflowService
from app.services.memory_store import MemoryBackend, MemoryStore
from app.services.metrics_snapshot_store import MetricsSnapshotStore
from app.services.model_router import ModelRouter
from app.services.multi_agent_orchestrator import MultiAgentOrchestrator
from app.services.onboarding_experiment_service import OnboardingExperimentService
from app.services.plan_build_service import PlanBuildService
from app.services.routing_policy_service import RoutingPolicyService
from app.services.ops_service import OpsService
from app.services.team_workspace_service import TeamWorkspaceService
from app.services.providers.base import BaseProvider
from app.services.providers.ollama_provider import OllamaProvider
from app.services.providers.openai_compat_provider import OpenAICompatProvider
from app.services.sqlite_memory_store import SQLiteMemoryStore
from app.services.sqlite_agent_run_store import SQLiteAgentRunStore
from app.services.eval_report_store import EvalReportStore
from app.services.orchestration_eval_report_store import OrchestrationEvalReportStore
from app.services.eval_service import EvalService
from app.services.finetune_service import FinetuneService
from app.services.finetune_adapter_resolver import FinetuneAdapterResolver
from app.services.finetune_trainer_service import FinetuneTrainerService
from app.services.patch_outcome_store import PatchOutcomeStore
from app.services.feedback_store import FeedbackStore
from app.services.sqlite_task_store import SQLiteTaskStore
from app.services.task_service import PlanningError, TaskService
from app.services.task_agent_assignment import resolve_primary_template_id, resolve_project_template_ids
from app.services.task_store import InMemoryTaskStore
from app.services.provider_circuit_breaker import ProviderCircuitBreaker
from app.services.quota_store import QuotaStore
from app.services.response_cache_store import ResponseCacheStore
from app.services.stage1_scheduler_service import Stage1SchedulerService
from app.services.daily_improvement_scheduler_service import DailyImprovementSchedulerService
from app.services.telemetry_store import TelemetryStore
from app.services.tooling_service import ToolingService
from app.services.training_signal_store import TrainingSignalStore
from app.services.alert_webhook_service import AlertWebhookService
from app.services.llm_caller_service import LlmCallerService
from app.services.reasoning_orchestrator_service import ReasoningOrchestratorService


@lru_cache
def _build_llm_caller_service() -> LlmCallerService:
    settings = get_settings()
    providers: dict[str, BaseProvider] = {
        "ollama": OllamaProvider(settings.ollama_base_url),
        "openai_compat": OpenAICompatProvider(
            settings.openai_compat_base_url,
            settings.openai_compat_api_key,
        ),
    }
    router = ModelRouter(settings, routing_policy=_build_routing_policy_service())
    return LlmCallerService(providers=providers, model_router=router)


def get_llm_caller_service() -> LlmCallerService:
    return _build_llm_caller_service()


@lru_cache
def _build_reasoning_orchestrator_service() -> ReasoningOrchestratorService:
    settings = get_settings()
    return ReasoningOrchestratorService(
        llm_caller=_build_llm_caller_service(),
        draft_model=settings.reasoning_draft_model or settings.fast_model,
        critic_model=settings.reasoning_critic_model or settings.frontier_fallback_model,
    )


def get_reasoning_orchestrator_service() -> ReasoningOrchestratorService:
    return _build_reasoning_orchestrator_service()


@lru_cache
def _build_chat_service() -> ChatService:
    settings = get_settings()
    providers: dict[str, BaseProvider] = {
        "ollama": OllamaProvider(settings.ollama_base_url),
        "openai_compat": OpenAICompatProvider(
            settings.openai_compat_base_url,
            settings.openai_compat_api_key,
        ),
    }
    router = ModelRouter(settings, routing_policy=_build_routing_policy_service())
    memory_store: MemoryBackend
    if settings.memory_backend == "sqlite":
        memory_store = SQLiteMemoryStore(
            db_path=settings.memory_sqlite_path,
            max_messages_per_session=settings.memory_max_messages,
        )
    else:
        memory_store = MemoryStore(max_messages_per_session=settings.memory_max_messages)
    circuit_breaker = ProviderCircuitBreaker(
        failure_threshold=settings.circuit_failure_threshold,
        cooldown_seconds=settings.circuit_cooldown_seconds,
    )
    response_cache = None
    if settings.response_cache_ttl_seconds > 0:
        response_cache = ResponseCacheStore(
            backend=settings.response_cache_backend,
            sqlite_path=settings.response_cache_sqlite_path,
        )
    telemetry = _build_telemetry_store()
    compactor = ContextCompactor(
        max_messages=settings.context_max_messages,
        max_chars=settings.context_max_chars,
        summary_max_chars=settings.context_summary_max_chars,
    )
    enrichment = _build_context_enrichment_service() if settings.context_enrichment_enabled else None
    return ChatService(
        router,
        providers,
        memory_store,
        circuit_breaker,
        cache_ttl_seconds=settings.response_cache_ttl_seconds,
        response_cache=response_cache,
        telemetry=telemetry,
        context_compactor=compactor,
        code_retrieval=_build_code_retrieval_service(),
        context_enrichment=enrichment,
        retrieval_enabled=settings.retrieval_enabled,
        provider_retry_attempts=settings.provider_retry_attempts,
        provider_retry_backoff_ms=settings.provider_retry_backoff_ms,
        dual_pass_enabled=settings.dual_pass_enabled,
        dual_pass_task_types=settings.dual_pass_task_types,
    )


def get_chat_service() -> ChatService:
    return _build_chat_service()


@lru_cache
def _build_agent_registry_store() -> AgentRegistryStore:
    settings = get_settings()
    return AgentRegistryStore(file_path=settings.agent_registry_file_path)


def get_agent_registry_store() -> AgentRegistryStore:
    return _build_agent_registry_store()


@lru_cache
def _build_agent_memory_store() -> AgentMemoryStore:
    settings = get_settings()
    return AgentMemoryStore(
        db_path=settings.agent_memory_sqlite_path,
        max_entries_per_agent=settings.agent_memory_max_entries,
    )


def get_agent_memory_store() -> AgentMemoryStore:
    return _build_agent_memory_store()


@lru_cache
def _build_training_signal_store() -> TrainingSignalStore:
    settings = get_settings()
    return TrainingSignalStore(
        file_path=settings.finetune_training_signals_path,
        min_output_chars=settings.finetune_min_signal_output_chars,
        enabled=settings.finetune_auto_capture_signals,
    )


def get_training_signal_store() -> TrainingSignalStore:
    return _build_training_signal_store()


@lru_cache
def _build_agent_service() -> AgentService:
    settings = get_settings()
    if settings.agent_run_backend == "sqlite":
        run_store = SQLiteAgentRunStore(db_path=settings.agent_run_sqlite_path)
    else:
        run_store = InMemoryAgentRunStore()
    return AgentService(
        chat_service=_build_chat_service(),
        registry=_build_agent_registry_store(),
        run_store=run_store,
        tooling=_build_tooling_service(),
        browser_workflow=_build_browser_workflow_service(),
        playwright_browser=_build_playwright_browser_service(),
        agent_memory_store=_build_agent_memory_store(),
        agent_loop_service=AgentLoopService(),
        max_concurrency=settings.agent_max_concurrency,
        max_queue_size=settings.agent_max_queue_size,
        run_max_attempts=settings.agent_run_max_attempts,
        run_retry_backoff_ms=settings.agent_run_retry_backoff_ms,
        run_timeout_seconds=settings.agent_run_timeout_seconds,
        queue_stuck_timeout_seconds=settings.agent_queue_stuck_timeout_seconds,
        max_events_per_run=settings.agent_run_max_events_per_run,
        max_response_chars=settings.agent_run_max_response_chars,
        retention_days=settings.agent_run_retention_days,
        training_signal_store=_build_training_signal_store(),
        patch_outcome_store=_build_patch_outcome_store(),
        verify_after_patch=settings.agent_verify_after_patch,
        verify_cmd=settings.agent_verify_cmd,
        verify_max_retries=settings.agent_verify_max_retries,
        auto_confirm_risky_tools=settings.agent_auto_confirm_risky,
        guardrail_service=_build_guardrail_service(),
        hook_service=_build_agent_hook_service(),
        skill_store=_build_skill_store(),
        skill_selector=_build_skill_selector_service(),
        search_provider=_build_search_provider(),
        mcp_registry=_build_mcp_registry_service(),
        trace_span_store=_build_trace_span_store(),
        context_enrichment=_build_context_enrichment_service(),
        guardrails_enabled=settings.guardrails_enabled,
        default_repo_profile_id=settings.finetune_repo_profile_id,
        policy_preset_service=_build_agent_policy_preset_service(),
        media_generation_service=_build_media_generation_service(),
        reasoning_orchestrator=_build_reasoning_orchestrator_service(),
    )


def get_agent_service() -> AgentService:
    return _build_agent_service()


@lru_cache
def _build_agent_eval_service() -> AgentEvalService:
    settings = get_settings()
    memory_store = _build_agent_memory_store()

    def seed_memory(agent_id: str, seed: str) -> None:
        memory_store.append(
            agent_id=agent_id,
            outcome="seed",
            summary=seed[:120],
            detail=seed,
            run_id=None,
        )

    return AgentEvalService(
        scenarios_path=settings.agent_eval_scenarios_path,
        agent_service=_build_agent_service(),
        memory_seed_fn=seed_memory,
    )


def get_agent_eval_service() -> AgentEvalService:
    return _build_agent_eval_service()


@lru_cache
def _build_agent_maintenance_scheduler_service() -> AgentMaintenanceSchedulerService:
    settings = get_settings()
    return AgentMaintenanceSchedulerService(
        agent_service=_build_agent_service(),
        telemetry_store=_build_telemetry_store(),
        metrics_snapshot_store=_build_metrics_snapshot_store(),
        enabled=settings.agent_maintenance_enabled,
        cleanup_interval_seconds=settings.agent_cleanup_interval_seconds,
        metrics_snapshot_interval_seconds=settings.agent_metrics_snapshot_interval_seconds,
        stale_run_timeout_seconds=settings.agent_stale_run_timeout_seconds,
    )


def get_agent_maintenance_scheduler_service() -> AgentMaintenanceSchedulerService:
    return _build_agent_maintenance_scheduler_service()


@lru_cache
def _build_patch_outcome_store() -> PatchOutcomeStore:
    settings = get_settings()
    return PatchOutcomeStore(
        file_path=settings.finetune_patch_outcomes_path,
        enabled=settings.finetune_capture_patch_reverts,
    )


def get_patch_outcome_store() -> PatchOutcomeStore:
    return _build_patch_outcome_store()


@lru_cache
def _build_tooling_service() -> ToolingService:
    settings = get_settings()
    signals = _build_training_signal_store()
    patches = _build_patch_outcome_store()

    def on_file_changed(path: str) -> None:
        if settings.finetune_capture_patch_reverts:
            try:
                patches.handle_file_changed(
                    path,
                    root_path=settings.retrieval_root_path,
                    training_signals=signals,
                )
            except Exception:  # noqa: BLE001
                pass
        if not settings.retrieval_auto_reindex:
            return
        try:
            _build_code_retrieval_service().reindex_path(path)
        except Exception:  # noqa: BLE001
            pass

    return ToolingService(
        root_path=settings.retrieval_root_path,
        on_file_changed=on_file_changed,
    )


def get_tooling_service() -> ToolingService:
    return _build_tooling_service()


@lru_cache
def _build_task_service() -> TaskService:
    settings = get_settings()
    tooling = _build_tooling_service()
    if settings.task_backend == "sqlite":
        store = SQLiteTaskStore(db_path=settings.task_sqlite_path)
    else:
        store = InMemoryTaskStore()
    agent_runner = _task_agent_runner if settings.task_use_agent else None
    return TaskService(
        tooling,
        store,
        telemetry=_build_telemetry_store(),
        training_signal_store=_build_training_signal_store(),
        agent_runner=agent_runner,
        use_agent_for_auto=settings.task_use_agent,
        task_agent_id=settings.task_agent_id,
        assignment_workspace=_build_assignment_workspace_service(),
        agent_registry=_build_agent_registry_store(),
        agent_templates=_build_agent_templates_store(),
    )


def _task_agent_runner(
    input_text: str,
    task_type,
    session_id: Optional[str],
    project_id: Optional[str],
    model: Optional[str] = None,
) -> str:
    from app.domain.schemas import AgentRunRequest, AgentRunState, TaskType

    settings = get_settings()
    service = get_agent_service()
    agent_id = _resolve_task_agent_id(
        input_text=input_text,
        requested_task_type=task_type,
        preferred_agent_id=settings.task_agent_id.strip(),
        project_id=project_id,
        service=service,
    )
    if not agent_id:
        raise PlanningError("No agent configured for TERMIT_TASK_USE_AGENT.")
    payload = AgentRunRequest(
        input=input_text,
        session_id=session_id,
        project_id=project_id,
        model=model,
    )
    queued = service.create_run(agent_id, payload)
    deadline = time.time() + 180
    while time.time() < deadline:
        run = service.get_run(queued.run_id)
        if run.state == AgentRunState.completed:
            return run.response or ""
        if run.state in {AgentRunState.failed, AgentRunState.cancelled}:
            raise PlanningError(run.error or f"Agent run finished with state={run.state.value}")
        time.sleep(0.2)
    raise PlanningError("Agent run timeout while handling task auto-mode.")


def _resolve_task_agent_id(
    *,
    input_text: str,
    requested_task_type,
    preferred_agent_id: str,
    project_id: Optional[str],
    service: AgentService,
) -> str:
    from app.domain.schemas import TaskType

    if preferred_agent_id:
        return preferred_agent_id

    agents = service.list_agents()
    effective_type = _infer_task_type_for_assignment(requested_task_type, input_text)
    selected = _pick_existing_agent_id(agents, effective_type, input_text)
    if selected:
        return selected

    templates = get_agent_templates_store()
    if project_id:
        for template_id in resolve_project_template_ids(effective_type, input_text):
            try:
                request = templates.to_create_request(template_id)
            except ValueError:
                continue
            existing = next(
                (item for item in agents if item.name == request.name and item.task_type == request.task_type),
                None,
            )
            if existing is not None:
                continue
            created = service.create_agent(request)
            agents.append(created)

    template_id = _pick_template_for_task(effective_type, input_text)
    if template_id:
        try:
            request = templates.to_create_request(template_id)
        except ValueError:
            request = None
        if request is not None:
            created = service.create_agent(request)
            return created.agent_id

    # Last fallback keeps previous behavior if templates are unavailable.
    typed = [item for item in agents if item.task_type == requested_task_type]
    if typed:
        return typed[0].agent_id
    if agents:
        return agents[0].agent_id
    return ""


def _infer_task_type_for_assignment(requested_task_type, input_text: str):
    from app.domain.schemas import TaskType

    if requested_task_type != TaskType.general:
        return requested_task_type

    text = input_text.lower()
    if any(term in text for term in ("online project", "deliverables", "journal", "assignment")):
        return TaskType.online_project
    if any(term in text for term in ("research", "источник", "sources", "web search", "http://", "https://")):
        return TaskType.online_research
    if any(term in text for term in ("image", "video", "storyboard", "render", "gif", "media", "tts")):
        return TaskType.creative_media
    if any(term in text for term in ("debug", "traceback", "error", "bugfix", "fix bug")):
        return TaskType.debug
    if any(term in text for term in ("review", "security audit", "audit", "vulnerability")):
        return TaskType.review
    if any(term in text for term in ("explain", "why", "how does")):
        return TaskType.explain
    return TaskType.coding


def _pick_existing_agent_id(agents: list, task_type, input_text: str) -> str:
    if not agents:
        return ""
    lowered = input_text.lower()

    def _score(agent) -> int:
        score = 0
        if agent.task_type == task_type:
            score += 100
        if task_type.value.startswith("online") and getattr(agent, "allow_online", False):
            score += 15
        name = (getattr(agent, "name", "") or "").lower()
        if "research" in lowered and "research" in name:
            score += 10
        if any(term in lowered for term in ("test", "tests", "unittest")) and "test" in name:
            score += 10
        if "ci" in lowered and "ci" in name:
            score += 10
        if any(term in lowered for term in ("security", "audit", "vulnerability")) and "security" in name:
            score += 10
        return score

    ranked = sorted(agents, key=_score, reverse=True)
    if _score(ranked[0]) > 0:
        return ranked[0].agent_id
    return ""


def _pick_template_for_task(task_type, input_text: str) -> str:
    return resolve_primary_template_id(task_type, input_text)


def get_task_service() -> TaskService:
    return _build_task_service()


@lru_cache
def _build_playwright_browser_service():
    from app.services.playwright_browser_service import PlaywrightBrowserService

    return PlaywrightBrowserService()


def get_playwright_browser_service():
    return _build_playwright_browser_service()


@lru_cache
def _build_browser_workflow_service() -> BrowserWorkflowService:
    settings = get_settings()
    backend = settings.browser_backend
    if backend == "playwright":
        pw = _build_playwright_browser_service()
        if pw.available():
            return BrowserWorkflowService(
                fetcher=pw.fetch_as_http,
                backend_label="playwright",
            )
    return BrowserWorkflowService(backend_label="httpx")


def get_browser_workflow_service() -> BrowserWorkflowService:
    return _build_browser_workflow_service()


@lru_cache
def _build_assignment_workspace_service():
    from app.services.assignment_workspace_service import AssignmentWorkspaceService

    settings = get_settings()
    return AssignmentWorkspaceService(settings.assignments_dir)


def get_assignment_workspace_service():
    return _build_assignment_workspace_service()


@lru_cache
def _build_quota_store() -> QuotaStore:
    settings = get_settings()
    return QuotaStore(db_path=settings.quota_sqlite_path)


def get_quota_store() -> QuotaStore:
    return _build_quota_store()


@lru_cache
def _build_feedback_store() -> FeedbackStore:
    settings = get_settings()
    return FeedbackStore(file_path=settings.feedback_file_path)


def get_feedback_store() -> FeedbackStore:
    return _build_feedback_store()


@lru_cache
def _build_beta_cohort_service():
    from app.services.beta_cohort_service import BetaCohortService

    settings = get_settings()
    feedback = _build_feedback_store()
    agent_service = _build_agent_service()

    def task_activity() -> list[tuple[str, str]]:
        store = SQLiteTaskStore(db_path=settings.task_sqlite_path)
        return [
            (task.session_id or task.task_id, task.created_at)
            for task in store.list_tasks(limit=5000)
        ]

    def run_activity() -> list[tuple[str, str]]:
        return [
            (run.session_id or run.run_id, run.created_at)
            for run in agent_service._run_store.list_runs(limit=5000)
        ]

    return BetaCohortService(
        feedback_entries_provider=lambda: feedback.list_entries(limit=5000),
        task_activity_provider=task_activity,
        run_activity_provider=run_activity,
        target_d30_retention=0.35,
    )


def get_beta_cohort_service():
    return _build_beta_cohort_service()


@lru_cache
def _build_eval_service() -> EvalService:
    settings = get_settings()
    from app.core.model_roles import resolve_cloud_teacher_model
    from app.services.eval_quality_judge_service import EvalQualityJudgeService

    llm_caller = _build_llm_caller_service()
    judge_model = settings.eval_quality_judge_model or resolve_cloud_teacher_model(settings)
    quality_judge = EvalQualityJudgeService(
        judge_model=judge_model,
        llm_caller=llm_caller.call,
    )
    return EvalService(
        scenarios_path=settings.eval_scenarios_path,
        task_service=_build_task_service(),
        tooling_service=_build_tooling_service(),
        browser_service=_build_browser_workflow_service(),
        telemetry=_build_telemetry_store(),
        report_store=EvalReportStore(file_path=settings.eval_report_file_path),
        retrieval_service=_build_code_retrieval_service(),
        extra_scenarios_path=settings.media_eval_scenarios_path,
        extra_scenarios_paths=[
            settings.eval_iq_scenarios_path,
            settings.eval_swe_scenarios_path,
            settings.eval_humaneval_scenarios_path,
        ],
        quality_judge=quality_judge,
        llm_caller=llm_caller,
        model_benchmark_scenarios_path=settings.eval_model_benchmark_scenarios_path,
    )


def get_eval_service() -> EvalService:
    return _build_eval_service()


@lru_cache
def _build_orchestration_eval_report_store() -> OrchestrationEvalReportStore:
    settings = get_settings()
    return OrchestrationEvalReportStore(file_path=settings.orchestration_eval_report_file_path)


def get_orchestration_eval_report_store() -> OrchestrationEvalReportStore:
    return _build_orchestration_eval_report_store()


@lru_cache
def _build_telemetry_store() -> TelemetryStore:
    settings = get_settings()
    return TelemetryStore(max_latency_points=settings.telemetry_max_latency_points)


def get_telemetry_store() -> TelemetryStore:
    return _build_telemetry_store()


@lru_cache
def _build_metrics_snapshot_store() -> MetricsSnapshotStore:
    settings = get_settings()
    return MetricsSnapshotStore(
        file_path=settings.metrics_snapshot_file_path,
        degrade_empty_response_rate=settings.degrade_empty_response_rate,
        degrade_fallback_rate=settings.degrade_fallback_rate,
    )


def get_metrics_snapshot_store() -> MetricsSnapshotStore:
    return _build_metrics_snapshot_store()


@lru_cache
def _build_local_runtime_service() -> LocalRuntimeService:
    settings = get_settings()
    required = LocalRuntimeService.collect_required_ollama_models(
        default_model=settings.default_model,
        code_model=settings.code_model,
        analysis_model=settings.analysis_model,
        retrieval_embed_model=settings.retrieval_embed_model,
    )
    from app.core.model_roles import teacher_ollama_model_names

    return LocalRuntimeService(
        ollama_base_url=settings.ollama_base_url,
        openai_compat_base_url=settings.openai_compat_base_url,
        required_ollama_models=required,
        retrieval_mode=settings.retrieval_mode,
        runtime_primary_model=settings.code_model,
        teacher_model=settings.teacher_model,
        teacher_fallback_model=settings.teacher_fallback_model,
        teacher_ollama_models=teacher_ollama_model_names(settings),
    )


def get_local_runtime_service() -> LocalRuntimeService:
    return _build_local_runtime_service()


@lru_cache
def _build_code_retrieval_service() -> CodeRetrievalService:
    settings = get_settings()
    return CodeRetrievalService(
        root_path=settings.retrieval_root_path,
        chunk_max_chars=settings.retrieval_chunk_max_chars,
        max_file_bytes=settings.retrieval_max_file_bytes,
        mode=settings.retrieval_mode,
        ollama_base_url=settings.ollama_base_url,
        embed_model=settings.retrieval_embed_model,
        embed_cache_path=settings.retrieval_embed_cache_path,
    )


def get_code_retrieval_service() -> CodeRetrievalService:
    return _build_code_retrieval_service()


@lru_cache
def _build_repo_map_service() -> RepoMapService:
    settings = get_settings()
    return RepoMapService(
        root_path=settings.retrieval_root_path,
        max_dirs=settings.repo_map_max_dirs,
    )


def get_repo_map_service() -> RepoMapService:
    return _build_repo_map_service()


@lru_cache
def _build_symbol_index_service() -> SymbolIndexService:
    settings = get_settings()
    return SymbolIndexService(root_path=settings.retrieval_root_path)


def get_symbol_index_service() -> SymbolIndexService:
    return _build_symbol_index_service()


@lru_cache
def _build_context_packing_service() -> ContextPackingService:
    settings = get_settings()
    return ContextPackingService(root_path=settings.retrieval_root_path)


@lru_cache
def _build_project_rules_store() -> ProjectRulesStore:
    settings = get_settings()
    return ProjectRulesStore(base_dir=settings.project_rules_dir)


def get_project_rules_store() -> ProjectRulesStore:
    return _build_project_rules_store()


@lru_cache
def _build_agent_templates_store() -> AgentTemplatesStore:
    settings = get_settings()
    return AgentTemplatesStore(file_path=settings.agent_templates_path)


def get_agent_templates_store() -> AgentTemplatesStore:
    return _build_agent_templates_store()


@lru_cache
def _build_context_enrichment_service() -> ContextEnrichmentService:
    settings = get_settings()
    return ContextEnrichmentService(
        repo_map=_build_repo_map_service(),
        context_packing=_build_context_packing_service(),
        symbol_index=_build_symbol_index_service(),
        retrieval=_build_code_retrieval_service(),
        rules_store=_build_project_rules_store(),
        skill_store=_build_skill_store(),
        repo_map_enabled=True,
        context_packing_enabled=True,
    )


def get_context_enrichment_service() -> ContextEnrichmentService:
    return _build_context_enrichment_service()


@lru_cache
def _build_ops_service() -> OpsService:
    settings = get_settings()
    quota_store = None
    if settings.auth_enabled and settings.api_keys:
        quota_store = _build_quota_store()
    return OpsService(settings=settings, quota_store=quota_store, tooling=_build_tooling_service())


def get_ops_service() -> OpsService:
    return _build_ops_service()


@lru_cache
def _build_team_workspace_service() -> TeamWorkspaceService:
    settings = get_settings()
    return TeamWorkspaceService(settings=settings, quota_store=_build_quota_store())


def get_team_workspace_service() -> TeamWorkspaceService:
    return _build_team_workspace_service()


@lru_cache
def _build_multi_agent_orchestrator() -> MultiAgentOrchestrator:
    settings = get_settings()
    return MultiAgentOrchestrator(
        task_service=_build_task_service(),
        chat_service=_build_chat_service(),
        tooling=_build_tooling_service(),
        code_retrieval=_build_code_retrieval_service(),
        openhands_contract_enabled=settings.orchestration_openhands_contract_enabled,
        tool_loop_execution_enabled=settings.orchestration_tool_loop_execution_enabled,
        eval_fixture_coder_enabled=settings.orchestration_eval_fixture_coder_enabled,
    )


def get_multi_agent_orchestrator() -> MultiAgentOrchestrator:
    return _build_multi_agent_orchestrator()


@lru_cache
def _build_plan_build_service() -> PlanBuildService:
    return PlanBuildService(
        agent_service=_build_agent_service(),
        registry=_build_agent_registry_store(),
        templates=_build_agent_templates_store(),
        trace_spans=_build_trace_span_store(),
    )


def get_plan_build_service() -> PlanBuildService:
    return _build_plan_build_service()


@lru_cache
def _build_finetune_adapter_resolver() -> FinetuneAdapterResolver:
    settings = get_settings()
    return FinetuneAdapterResolver(
        adapters_path=settings.finetune_adapters_path,
        adapters_dir=settings.finetune_adapters_dir,
    )


def get_finetune_adapter_resolver() -> FinetuneAdapterResolver:
    return _build_finetune_adapter_resolver()


@lru_cache
def _build_routing_policy_service() -> RoutingPolicyService:
    settings = get_settings()
    return RoutingPolicyService(
        repo_profiles_path=settings.repo_model_profiles_path,
        benchmarks_path=settings.routing_benchmarks_path,
        adapter_resolver=_build_finetune_adapter_resolver(),
    )


def get_routing_policy_service() -> RoutingPolicyService:
    return _build_routing_policy_service()


@lru_cache
def _build_finetune_trainer_service() -> FinetuneTrainerService:
    settings = get_settings()
    return FinetuneTrainerService(
        modelfiles_dir=settings.finetune_modelfiles_dir,
        adapters_dir=settings.finetune_adapters_dir,
        ollama_bin=settings.finetune_ollama_bin,
        ollama_base_url=settings.ollama_base_url,
        default_output_model=settings.finetune_output_model,
        trainer_mode=settings.finetune_trainer,
        train_timeout_seconds=settings.finetune_train_timeout_seconds,
        hf_dry_run=settings.finetune_hf_dry_run,
        hf_epochs=settings.finetune_hf_epochs,
        hf_lora_rank=settings.finetune_hf_lora_rank,
        hf_max_samples=settings.finetune_hf_max_samples,
        hf_auto_gguf=settings.finetune_hf_auto_gguf,
        hf_auto_ollama=settings.finetune_hf_auto_ollama,
        llama_cpp_path=settings.finetune_llama_cpp_path,
    )


def get_finetune_trainer_service() -> FinetuneTrainerService:
    return _build_finetune_trainer_service()


@lru_cache
def _build_finetune_service() -> FinetuneService:
    from app.domain.schemas import FinetuneStage1RunRequest

    settings = get_settings()
    signal_store = _build_training_signal_store()

    def _post_eval_runner(request: FinetuneStage1RunRequest) -> dict[str, object]:
        return _build_eval_service().run_suite(
            category=request.eval_category,
            limit=request.eval_limit or 24,
            persist_report=True,
        )

    return FinetuneService(
        datasets_dir=settings.finetune_datasets_dir,
        jobs_path=settings.finetune_jobs_path,
        adapters_path=settings.finetune_adapters_path,
        pipelines_path=settings.finetune_pipelines_path,
        cycle_events_path=settings.finetune_cycle_events_path,
        feedback_file_path=settings.feedback_file_path,
        task_sqlite_path=settings.task_sqlite_path,
        agent_run_sqlite_path=settings.agent_run_sqlite_path,
        memory_sqlite_path=settings.memory_sqlite_path,
        training_signals_path=settings.finetune_training_signals_path,
        eval_report_file_path=settings.eval_report_file_path,
        repo_profiles_path=settings.repo_model_profiles_path,
        pipeline_max_concurrency=settings.finetune_pipeline_max_concurrency,
        pipeline_stuck_timeout_seconds=settings.finetune_pipeline_stuck_timeout_seconds,
        trainer=_build_finetune_trainer_service(),
        auto_train_after_pipeline=settings.finetune_auto_train,
        auto_register_after_train=settings.finetune_auto_register_after_train,
        auto_post_eval=settings.finetune_auto_post_eval,
        post_eval_runner=_post_eval_runner,
        training_signal_store=signal_store,
        regression_gate_enabled=settings.finetune_regression_gate_enabled,
        regression_require_post_eval=settings.finetune_regression_require_post_eval,
        max_train_regression=settings.finetune_max_train_regression,
        shadow_traffic_percent=settings.finetune_shadow_traffic_percent,
    )


@lru_cache
def _build_alert_webhook_service() -> AlertWebhookService:
    settings = get_settings()
    return AlertWebhookService(webhook_url=settings.alert_webhook_url)


def get_alert_webhook_service() -> AlertWebhookService:
    return _build_alert_webhook_service()


def get_finetune_service() -> FinetuneService:
    return _build_finetune_service()


@lru_cache
def _build_stage1_scheduler_service() -> Stage1SchedulerService:
    settings = get_settings()
    return Stage1SchedulerService(
        settings=settings,
        finetune_service=_build_finetune_service(),
        eval_service=_build_eval_service(),
    )


def get_stage1_scheduler_service() -> Stage1SchedulerService:
    return _build_stage1_scheduler_service()


@lru_cache
def _build_daily_improvement_service():
    from app.services.daily_improvement_service import DailyImprovementService

    settings = get_settings()
    return DailyImprovementService(
        settings=settings,
        agent_service=_build_agent_service(),
        eval_service=_build_eval_service(),
        kpi_gate_service=_build_desktop_kpi_gate_service(),
        finetune_service=_build_finetune_service(),
    )


def get_daily_improvement_service():
    return _build_daily_improvement_service()


@lru_cache
def _build_daily_improvement_scheduler_service() -> DailyImprovementSchedulerService:
    settings = get_settings()
    return DailyImprovementSchedulerService(
        settings=settings,
        improvement_service=_build_daily_improvement_service(),
    )


def get_daily_improvement_scheduler_service() -> DailyImprovementSchedulerService:
    return _build_daily_improvement_scheduler_service()


@lru_cache
def _build_skill_store() -> SkillStore:
    settings = get_settings()
    return SkillStore(settings.skills_dir)


def get_skill_store() -> SkillStore:
    return _build_skill_store()


@lru_cache
def _build_skill_selector_service() -> SkillSelectorService:
    settings = get_settings()
    return SkillSelectorService(
        _build_skill_store(),
        max_skills=settings.skill_auto_select_max,
        min_score=settings.skill_auto_select_min_score,
        enabled=settings.skill_auto_select_enabled,
    )


def get_skill_selector_service() -> SkillSelectorService:
    return _build_skill_selector_service()


@lru_cache
def _build_guardrail_service() -> GuardrailService:
    settings = get_settings()
    return GuardrailService(max_patch_chars=settings.guardrails_max_patch_chars)


def get_guardrail_service() -> GuardrailService:
    return _build_guardrail_service()


@lru_cache
def _build_agent_hook_service() -> AgentHookService:
    settings = get_settings()
    webhook = settings.hooks_webhook_url or settings.alert_webhook_url
    return AgentHookService(
        config_path=settings.hooks_config_path,
        webhook_url=webhook,
        enabled=settings.hooks_enabled,
    )


def get_agent_hook_service() -> AgentHookService:
    return _build_agent_hook_service()


@lru_cache
def _build_trace_span_store() -> TraceSpanStore:
    settings = get_settings()
    return TraceSpanStore(settings.trace_spans_db_path)


def get_trace_span_store() -> TraceSpanStore:
    return _build_trace_span_store()


@lru_cache
def _build_search_provider():
    settings = get_settings()
    return build_search_provider(
        settings.search_api_url,
        settings.search_api_key,
        provider=settings.search_provider,
    )


def get_search_provider():
    return _build_search_provider()


@lru_cache
def _build_mcp_registry_service() -> McpRegistryService:
    settings = get_settings()
    return McpRegistryService(settings.mcp_registry_path)


def get_mcp_registry_service() -> McpRegistryService:
    return _build_mcp_registry_service()


def _schedule_enqueue(agent_id: str, payload) -> str:
    return get_agent_service().create_run(agent_id, payload).run_id


@lru_cache
def _build_agent_schedule_service() -> AgentScheduleService:
    settings = get_settings()
    service = AgentScheduleService(
        db_path=settings.agent_schedules_db_path,
        enqueue_fn=_schedule_enqueue,
        poll_interval_seconds=settings.agent_schedules_poll_seconds,
    )
    if settings.agent_schedules_enabled:
        service.start()
    return service


def get_agent_schedule_service() -> AgentScheduleService:
    return _build_agent_schedule_service()


@lru_cache
def _build_automation_control_service():
    from app.services.automation_control_service import AutomationControlService

    return AutomationControlService(
        stage1_scheduler=get_stage1_scheduler_service(),
        daily_scheduler=get_daily_improvement_scheduler_service(),
        maintenance_scheduler=get_agent_maintenance_scheduler_service(),
        agent_schedule_service=get_agent_schedule_service(),
        project_root=str(Path(__file__).resolve().parents[2]),
    )


def get_automation_control_service():
    return _build_automation_control_service()


@lru_cache
def _build_agent_policy_preset_service():
    from app.services.agent_policy_preset_service import AgentPolicyPresetService

    settings = get_settings()
    return AgentPolicyPresetService(settings.desktop_policy_presets_path)


def get_agent_policy_preset_service():
    return _build_agent_policy_preset_service()


@lru_cache
def _build_desktop_accelerator_service():
    from app.services.desktop_accelerator_service import DesktopAcceleratorService

    settings = get_settings()
    agent_service = _build_agent_service()
    eval_service = _build_eval_service()

    def run_lookup(run_id: str) -> dict[str, object] | None:
        try:
            record = agent_service.get_run(run_id)
        except Exception:
            return None
        return record.model_dump()

    def eval_suite_runner(category: str | None, limit: int | None) -> dict[str, object]:
        report = eval_service.run_suite(category=category, limit=limit, persist_report=True)
        return {str(key): value for key, value in report.items()}

    return DesktopAcceleratorService(
        settings.desktop_state_dir,
        run_lookup=run_lookup,
        eval_suite_runner=eval_suite_runner,
    )


def get_desktop_accelerator_service():
    return _build_desktop_accelerator_service()


@lru_cache
def _build_desktop_workflow_telemetry_service():
    from app.services.desktop_workflow_telemetry_service import DesktopWorkflowTelemetryService

    settings = get_settings()
    return DesktopWorkflowTelemetryService(settings.desktop_state_dir)


def get_desktop_workflow_telemetry_service():
    return _build_desktop_workflow_telemetry_service()


@lru_cache
def _build_onboarding_experiment_service() -> OnboardingExperimentService:
    return OnboardingExperimentService()


def get_onboarding_experiment_service() -> OnboardingExperimentService:
    return _build_onboarding_experiment_service()


@lru_cache
def _build_desktop_kpi_gate_service():
    from app.services.desktop_kpi_gate_service import DesktopKpiGateService

    settings = get_settings()
    eval_service = _build_eval_service()
    agent_service = _build_agent_service()
    telemetry = _build_desktop_workflow_telemetry_service()

    def eval_dashboard_provider() -> dict[str, object]:
        return eval_service.build_dashboard(report_limit=5)

    def agent_metrics_provider() -> dict[str, object]:
        return agent_service.queue_metrics()

    def telemetry_summary_provider() -> dict[str, object]:
        return telemetry.summarize(settings.finetune_patch_outcomes_path)

    def metrics_summary_provider() -> dict[str, object]:
        return _build_telemetry_store().snapshot().model_dump()

    def beta_metrics_provider() -> dict[str, object]:
        metrics = _build_beta_cohort_service().build_metrics()
        metrics["feedback_total"] = _build_feedback_store().summarize().get("total", 0)
        return metrics

    def onboarding_metrics_provider() -> dict[str, object]:
        return _build_onboarding_experiment_service().summarize(telemetry.list_events())

    def mcp_metrics_provider() -> dict[str, object]:
        raw = agent_service.queue_metrics()
        tool_loop_runs = int(raw.get("tool_loop_runs", 0) or 0)
        mcp_active = int(raw.get("mcp_active_runs", 0) or 0)
        adoption = round(mcp_active / tool_loop_runs, 4) if tool_loop_runs else None
        return {
            **{key: raw.get(key) for key in (
                "mcp_context_inject_total",
                "mcp_prompt_inject_total",
                "mcp_invoke_total",
                "mcp_read_resource_total",
                "mcp_get_prompt_total",
                "mcp_tool_calls_total",
                "mcp_inject_runs",
                "mcp_active_runs",
                "mcp_inject_rate",
                "tool_loop_runs",
            )},
            "mcp_adoption_rate": adoption,
        }

    return DesktopKpiGateService(
        settings.desktop_north_star_path,
        eval_dashboard_provider=eval_dashboard_provider,
        agent_metrics_provider=agent_metrics_provider,
        telemetry_summary_provider=telemetry_summary_provider,
        metrics_summary_provider=metrics_summary_provider,
        beta_metrics_provider=beta_metrics_provider,
        onboarding_metrics_provider=onboarding_metrics_provider,
        mcp_metrics_provider=mcp_metrics_provider,
    )


def get_desktop_kpi_gate_service():
    return _build_desktop_kpi_gate_service()


@lru_cache
def _build_media_asset_store():
    from app.services.media_asset_store import MediaAssetStore

    settings = get_settings()
    return MediaAssetStore(settings.media_storage)


@lru_cache
def _build_media_generation_service():
    from app.services.media_generation_service import MediaGenerationService

    settings = get_settings()
    return MediaGenerationService(
        asset_store=_build_media_asset_store(),
        enabled=settings.media_enabled,
        trace_span_store=_build_trace_span_store(),
        max_cost_usd=settings.media_max_cost_usd,
        confirm_cost_usd=settings.media_confirm_cost_usd,
        image_provider_name=settings.media_image_provider,
        openai_api_key=settings.openai_api_key,
        openai_base_url=settings.openai_api_base_url,
        openai_image_model=settings.media_image_model,
        image_cost_usd=settings.media_image_cost_usd,
        tts_cost_usd=settings.media_tts_cost_usd,
        transcribe_cost_usd=settings.media_transcribe_cost_usd,
        tts_voice=settings.media_tts_voice,
        ffmpeg_path=settings.ffmpeg_path,
        ffprobe_path=settings.ffprobe_path,
        jobs_db_path=settings.media_jobs_db_path,
        i2v_provider=settings.media_i2v_provider,
        fal_api_key=settings.fal_api_key,
        media_public_base_url=settings.media_public_base_url,
        i2v_cost_usd=settings.media_i2v_cost_usd,
        brand_kits_dir=settings.media_brand_kits_dir,
    )


def get_media_generation_service():
    return _build_media_generation_service()
