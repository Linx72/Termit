from functools import lru_cache
from typing import Optional

from app.core.config import get_settings
from app.services.agent_registry_store import AgentRegistryStore
from app.services.agent_service import AgentService
from app.services.agent_run_store import InMemoryAgentRunStore
from app.services.agent_maintenance_scheduler_service import AgentMaintenanceSchedulerService
from app.services.agent_memory_store import AgentMemoryStore
from app.services.agent_eval_service import AgentEvalService
from app.services.agent_loop_service import AgentLoopService
from app.services.local_runtime_service import LocalRuntimeService
from app.services.chat_service import ChatService
from app.services.code_retrieval_service import CodeRetrievalService
from app.services.context_compaction import ContextCompactor
from app.services.browser_workflow_service import BrowserWorkflowService
from app.services.memory_store import MemoryBackend, MemoryStore
from app.services.metrics_snapshot_store import MetricsSnapshotStore
from app.services.model_router import ModelRouter
from app.services.multi_agent_orchestrator import MultiAgentOrchestrator
from app.services.routing_policy_service import RoutingPolicyService
from app.services.ops_service import OpsService
from app.services.team_workspace_service import TeamWorkspaceService
from app.services.providers.base import BaseProvider
from app.services.providers.ollama_provider import OllamaProvider
from app.services.providers.openai_compat_provider import OpenAICompatProvider
from app.services.sqlite_memory_store import SQLiteMemoryStore
from app.services.sqlite_agent_run_store import SQLiteAgentRunStore
from app.services.eval_report_store import EvalReportStore
from app.services.eval_service import EvalService
from app.services.finetune_service import FinetuneService
from app.services.finetune_trainer_service import FinetuneTrainerService
from app.services.feedback_store import FeedbackStore
from app.services.sqlite_task_store import SQLiteTaskStore
from app.services.task_service import PlanningError, TaskService
from app.services.task_store import InMemoryTaskStore
from app.services.provider_circuit_breaker import ProviderCircuitBreaker
from app.services.quota_store import QuotaStore
from app.services.response_cache_store import ResponseCacheStore
from app.services.stage1_scheduler_service import Stage1SchedulerService
from app.services.telemetry_store import TelemetryStore
from app.services.tooling_service import ToolingService
from app.services.training_signal_store import TrainingSignalStore
from app.services.alert_webhook_service import AlertWebhookService
from app.domain.schemas import FinetuneStage1RunRequest


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
        agent_memory_store=_build_agent_memory_store(),
        agent_loop_service=AgentLoopService(),
        max_concurrency=settings.agent_max_concurrency,
        max_queue_size=settings.agent_max_queue_size,
        run_max_attempts=settings.agent_run_max_attempts,
        run_retry_backoff_ms=settings.agent_run_retry_backoff_ms,
        max_events_per_run=settings.agent_run_max_events_per_run,
        max_response_chars=settings.agent_run_max_response_chars,
        retention_days=settings.agent_run_retention_days,
        training_signal_store=_build_training_signal_store(),
        verify_after_patch=settings.agent_verify_after_patch,
        verify_cmd=settings.agent_verify_cmd,
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
    )


def get_agent_maintenance_scheduler_service() -> AgentMaintenanceSchedulerService:
    return _build_agent_maintenance_scheduler_service()


@lru_cache
def _build_tooling_service() -> ToolingService:
    return ToolingService(root_path=".")


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
    )


def _task_agent_runner(input_text: str, task_type, session_id: Optional[str]) -> str:
    import asyncio

    from app.domain.schemas import AgentRunRequest, TaskType

    settings = get_settings()
    service = get_agent_service()
    agent_id = settings.task_agent_id.strip()
    if not agent_id:
        agents = service.list_agents()
        typed = [item for item in agents if item.task_type == task_type]
        if typed:
            agent_id = typed[0].agent_id
        elif agents:
            agent_id = agents[0].agent_id
    if not agent_id:
        raise PlanningError("No agent configured for TERMIT_TASK_USE_AGENT.")
    payload = AgentRunRequest(input=input_text, session_id=session_id)
    result = asyncio.run(service.run_agent(agent_id, payload))
    return result.response or ""


def get_task_service() -> TaskService:
    return _build_task_service()


@lru_cache
def _build_browser_workflow_service() -> BrowserWorkflowService:
    return BrowserWorkflowService()


def get_browser_workflow_service() -> BrowserWorkflowService:
    return _build_browser_workflow_service()


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
def _build_eval_service() -> EvalService:
    settings = get_settings()
    return EvalService(
        scenarios_path=settings.eval_scenarios_path,
        task_service=_build_task_service(),
        tooling_service=_build_tooling_service(),
        browser_service=_build_browser_workflow_service(),
        telemetry=_build_telemetry_store(),
        report_store=EvalReportStore(file_path=settings.eval_report_file_path),
    )


def get_eval_service() -> EvalService:
    return _build_eval_service()


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
    return LocalRuntimeService(
        ollama_base_url=settings.ollama_base_url,
        openai_compat_base_url=settings.openai_compat_base_url,
        required_ollama_models=required,
        retrieval_mode=settings.retrieval_mode,
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
    return MultiAgentOrchestrator(
        task_service=_build_task_service(),
        chat_service=_build_chat_service(),
    )


def get_multi_agent_orchestrator() -> MultiAgentOrchestrator:
    return _build_multi_agent_orchestrator()


@lru_cache
def _build_routing_policy_service() -> RoutingPolicyService:
    settings = get_settings()
    return RoutingPolicyService(
        repo_profiles_path=settings.repo_model_profiles_path,
        benchmarks_path=settings.routing_benchmarks_path,
    )


def get_routing_policy_service() -> RoutingPolicyService:
    return _build_routing_policy_service()


@lru_cache
def _build_finetune_trainer_service() -> FinetuneTrainerService:
    settings = get_settings()
    return FinetuneTrainerService(
        modelfiles_dir=settings.finetune_modelfiles_dir,
        ollama_bin=settings.finetune_ollama_bin,
        default_output_model=settings.finetune_output_model,
        trainer_mode=settings.finetune_trainer,
        train_timeout_seconds=settings.finetune_train_timeout_seconds,
    )


def get_finetune_trainer_service() -> FinetuneTrainerService:
    return _build_finetune_trainer_service()


@lru_cache
def _build_finetune_service() -> FinetuneService:
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
        feedback_file_path=settings.feedback_file_path,
        task_sqlite_path=settings.task_sqlite_path,
        agent_run_sqlite_path=settings.agent_run_sqlite_path,
        memory_sqlite_path=settings.memory_sqlite_path,
        training_signals_path=settings.finetune_training_signals_path,
        eval_report_file_path=settings.eval_report_file_path,
        repo_profiles_path=settings.repo_model_profiles_path,
        pipeline_max_concurrency=settings.finetune_pipeline_max_concurrency,
        trainer=_build_finetune_trainer_service(),
        auto_train_after_pipeline=settings.finetune_auto_train,
        auto_register_after_train=settings.finetune_auto_register_after_train,
        auto_post_eval=settings.finetune_auto_post_eval,
        post_eval_runner=_post_eval_runner,
        training_signal_store=signal_store,
        regression_gate_enabled=settings.finetune_regression_gate_enabled,
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
