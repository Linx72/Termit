from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import Settings, get_settings
from app.domain.schemas import (
    AgentAlertThresholds,
    AgentRunsCleanupRequest,
    AgentRunsCleanupResponse,
    AgentRunsMetricsResponse,
    DailyImprovementPlanResponse,
    DailyImprovementRunResponse,
    DailyImprovementStatusResponse,
    AutomationPrefsResponse,
    AutomationPrefsUpdateRequest,
    AutomationToggleItem,
    OpsIncidentDrillResponse,
    OpsReadinessResponse,
    QuotaResetRequest,
    QuotaResetResponse,
    QuotaSummaryResponse,
    QuotaEntrySummary,
    OrchestrationEvalReportListResponse,
    OrchestrationEvalTrendResponse,
)
from app.services.alert_health_service import evaluate_agent_health
from app.services.ops_service import OpsService
from app.services.agent_service import AgentService
from app.services.multi_agent_orchestrator import MultiAgentOrchestrator
from app.services.agent_maintenance_scheduler_service import AgentMaintenanceSchedulerService
from app.services.daily_improvement_scheduler_service import DailyImprovementSchedulerService
from app.services.quota_store import QuotaStore
from app.services.automation_control_service import AutomationControlService
from app.services.orchestration_eval_report_store import OrchestrationEvalReportStore
from app.state import (
    get_agent_maintenance_scheduler_service,
    get_agent_service,
    get_automation_control_service,
    get_chat_service,
    get_daily_improvement_scheduler_service,
    get_multi_agent_orchestrator,
    get_orchestration_eval_report_store,
    get_ops_service,
    get_quota_store,
)

router = APIRouter(prefix="/api/ops", tags=["ops"])


def _agent_runs_metrics_payload(
    service: AgentService,
    settings: Settings,
    orchestration: MultiAgentOrchestrator | None = None,
) -> AgentRunsMetricsResponse:
    raw = service.queue_metrics()
    if orchestration is not None:
        raw.update(orchestration.metrics_snapshot())
    thresholds = AgentAlertThresholds(
        queue_utilization_percent=settings.agent_alert_queue_utilization_percent,
        dead_letter_rate=settings.agent_alert_dead_letter_rate,
        min_worker_alive_ratio=settings.agent_alert_min_worker_alive_ratio,
        min_verify_pass_rate=settings.agent_alert_min_verify_pass_rate,
    )
    health_status, health_reasons, dead_letter_rate = evaluate_agent_health(raw, thresholds)
    return AgentRunsMetricsResponse.model_validate(
        {
            **raw,
            "dead_letter_rate": dead_letter_rate,
            "health_status": health_status,
            "health_reasons": health_reasons,
            "active_thresholds": thresholds,
        }
    )


@router.get("/readiness", response_model=OpsReadinessResponse)
async def readiness(
    ops: OpsService = Depends(get_ops_service),
    service: AgentService = Depends(get_agent_service),
) -> OpsReadinessResponse:
    chat = get_chat_service()
    return await ops.readiness(
        providers_status_cb=chat.providers_status,
        agent_metrics_cb=service.queue_metrics,
    )


@router.post("/incident-drill", response_model=OpsIncidentDrillResponse)
async def incident_drill(
    ops: OpsService = Depends(get_ops_service),
) -> OpsIncidentDrillResponse:
    chat = get_chat_service()
    return await ops.incident_drill(providers_status_cb=chat.providers_status)


@router.get("/quota-summary", response_model=QuotaSummaryResponse)
async def quota_summary(
    settings: Settings = Depends(get_settings),
    quota_store: QuotaStore = Depends(get_quota_store),
) -> QuotaSummaryResponse:
    if not settings.auth_enabled or not settings.api_keys:
        return QuotaSummaryResponse(auth_enabled=False, entries=[])

    usage_map = quota_store.list_usage_for_day()
    entries: list[QuotaEntrySummary] = []
    for api_key, key_config in settings.api_keys.items():
        used = usage_map.get(api_key, 0)
        remaining = max(key_config.daily_quota - used, 0)
        percent = round((used / key_config.daily_quota) * 100, 2) if key_config.daily_quota else 0.0
        entries.append(
            QuotaEntrySummary(
                key_hint=OpsService.mask_api_key(api_key),
                role=key_config.role,
                team=key_config.team,
                used=used,
                limit=key_config.daily_quota,
                remaining=remaining,
                usage_percent=percent,
            )
        )
    entries.sort(key=lambda item: item.usage_percent, reverse=True)
    return QuotaSummaryResponse(auth_enabled=True, entries=entries)


@router.post("/quota/reset", response_model=QuotaResetResponse)
async def reset_quota(
    payload: QuotaResetRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    quota_store: QuotaStore = Depends(get_quota_store),
) -> QuotaResetResponse:
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Auth is disabled.")

    caller_role = getattr(request.state, "api_role", None)
    if caller_role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required.")

    if payload.api_key not in settings.api_keys:
        raise HTTPException(status_code=404, detail="Unknown API key.")

    reset = quota_store.reset_usage(payload.api_key)
    return QuotaResetResponse(
        api_key=OpsService.mask_api_key(payload.api_key),
        reset=reset,
        message="Quota reset for today." if reset else "No usage records found for today.",
    )


@router.get("/agent-runs/metrics", response_model=AgentRunsMetricsResponse)
async def agent_runs_metrics(
    settings: Settings = Depends(get_settings),
    service: AgentService = Depends(get_agent_service),
    orchestration: MultiAgentOrchestrator = Depends(get_multi_agent_orchestrator),
) -> AgentRunsMetricsResponse:
    return _agent_runs_metrics_payload(service, settings, orchestration)


@router.get("/orchestration/reports", response_model=OrchestrationEvalReportListResponse)
async def orchestration_reports(
    limit: int = 20,
    store: OrchestrationEvalReportStore = Depends(get_orchestration_eval_report_store),
) -> OrchestrationEvalReportListResponse:
    reports = store.list_recent(limit=limit)
    return OrchestrationEvalReportListResponse(reports=reports, total=len(reports))


@router.get("/orchestration/trend", response_model=OrchestrationEvalTrendResponse)
async def orchestration_trend(
    limit: int = 24,
    store: OrchestrationEvalReportStore = Depends(get_orchestration_eval_report_store),
) -> OrchestrationEvalTrendResponse:
    return OrchestrationEvalTrendResponse(points=store.trend_points(limit=limit))


@router.post("/agent-runs/cleanup", response_model=AgentRunsCleanupResponse)
async def cleanup_agent_runs(
    payload: AgentRunsCleanupRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    service: AgentService = Depends(get_agent_service),
) -> AgentRunsCleanupResponse:
    if settings.auth_enabled:
        caller_role = getattr(request.state, "api_role", "viewer")
        if caller_role != "admin":
            raise HTTPException(status_code=403, detail="Admin role required.")
    result = service.cleanup_runs(
        retention_days=payload.retention_days,
        dry_run=payload.dry_run,
    )
    return AgentRunsCleanupResponse.model_validate(result)


@router.get("/agent-runs/maintenance")
async def agent_runs_maintenance_status(
    request: Request,
    settings: Settings = Depends(get_settings),
    scheduler: AgentMaintenanceSchedulerService = Depends(get_agent_maintenance_scheduler_service),
) -> dict[str, object]:
    if settings.auth_enabled:
        caller_role = getattr(request.state, "api_role", "viewer")
        if caller_role != "admin":
            raise HTTPException(status_code=403, detail="Admin role required.")
    return scheduler.status()


@router.post("/agent-runs/maintenance/cleanup-now", response_model=AgentRunsCleanupResponse)
async def agent_runs_maintenance_cleanup_now(
    payload: AgentRunsCleanupRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    scheduler: AgentMaintenanceSchedulerService = Depends(get_agent_maintenance_scheduler_service),
) -> AgentRunsCleanupResponse:
    if settings.auth_enabled:
        caller_role = getattr(request.state, "api_role", "viewer")
        if caller_role != "admin":
            raise HTTPException(status_code=403, detail="Admin role required.")
    result = scheduler.run_cleanup_once(dry_run=payload.dry_run)
    return AgentRunsCleanupResponse.model_validate(result)


@router.post("/alerts/dispatch")
async def dispatch_ops_alerts(
    request: Request,
    settings: Settings = Depends(get_settings),
    agent_service: AgentService = Depends(get_agent_service),
    orchestration: MultiAgentOrchestrator = Depends(get_multi_agent_orchestrator),
) -> dict[str, object]:
    from app.state import get_alert_webhook_service

    if settings.auth_enabled:
        caller_role = getattr(request.state, "api_role", "viewer")
        if caller_role not in {"admin", "operator"}:
            raise HTTPException(status_code=403, detail="Operator role required.")

    metrics = _agent_runs_metrics_payload(agent_service, settings, orchestration)
    webhook = get_alert_webhook_service()
    if not webhook.enabled:
        return {"sent": False, "reason": "webhook_not_configured", "health_status": metrics.health_status}

    detail = "; ".join(metrics.health_reasons) if metrics.health_reasons else "All checks passed."
    result = webhook.send(
        title="Termit agent ops alert",
        status=str(metrics.health_status),
        detail=detail,
        payload={
            "dead_letter_rate": metrics.dead_letter_rate,
            "tool_loop_verify_pass_rate": metrics.tool_loop_verify_pass_rate,
            "min_verify_pass_rate": metrics.active_thresholds.min_verify_pass_rate,
        },
    )
    return {"health_status": metrics.health_status, **result}


def _require_operator(request: Request, settings: Settings) -> None:
    if not settings.auth_enabled:
        return
    caller_role = getattr(request.state, "api_role", "viewer")
    if caller_role not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Operator role required.")


@router.get("/automation", response_model=AutomationPrefsResponse)
async def automation_prefs(
    service: AutomationControlService = Depends(get_automation_control_service),
) -> AutomationPrefsResponse:
    payload = service.snapshot()
    toggles = [
        AutomationToggleItem(**item)
        for item in payload.get("toggles", [])
        if isinstance(item, dict)
    ]
    return AutomationPrefsResponse(
        env_path=str(payload.get("env_path", "")),
        automatic_mode_enabled=bool(payload.get("automatic_mode_enabled")),
        toggles=toggles,
        schedulers=dict(payload.get("schedulers", {})),
    )


@router.patch("/automation", response_model=AutomationPrefsResponse)
async def automation_prefs_update(
    body: AutomationPrefsUpdateRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
    service: AutomationControlService = Depends(get_automation_control_service),
) -> AutomationPrefsResponse:
    _require_operator(request, settings)
    if body.automatic_mode_enabled is not None:
        payload = service.set_automatic_mode(bool(body.automatic_mode_enabled))
    elif body.toggles:
        payload = service.apply(body.toggles)
    else:
        payload = service.snapshot()
    toggles = [
        AutomationToggleItem(**item)
        for item in payload.get("toggles", [])
        if isinstance(item, dict)
    ]
    return AutomationPrefsResponse(
        env_path=str(payload.get("env_path", "")),
        automatic_mode_enabled=bool(payload.get("automatic_mode_enabled")),
        toggles=toggles,
        schedulers=dict(payload.get("schedulers", {})),
        applied=[str(item) for item in payload.get("applied", [])],
        restart_recommended=bool(payload.get("restart_recommended")),
    )


@router.get("/daily-improvement/status", response_model=DailyImprovementStatusResponse)
async def daily_improvement_status(
    scheduler: DailyImprovementSchedulerService = Depends(get_daily_improvement_scheduler_service),
) -> DailyImprovementStatusResponse:
    return DailyImprovementStatusResponse(**scheduler.status())


@router.get("/daily-improvement/plan", response_model=DailyImprovementPlanResponse)
async def daily_improvement_plan(
    request: Request,
    settings: Settings = Depends(get_settings),
    scheduler: DailyImprovementSchedulerService = Depends(get_daily_improvement_scheduler_service),
) -> DailyImprovementPlanResponse:
    if settings.auth_enabled:
        caller_role = getattr(request.state, "api_role", "viewer")
        if caller_role not in {"admin", "operator"}:
            raise HTTPException(status_code=403, detail="Operator role required.")
    return DailyImprovementPlanResponse(**scheduler.preview_plan())


@router.post("/daily-improvement/trigger", response_model=DailyImprovementRunResponse)
async def daily_improvement_trigger(
    request: Request,
    settings: Settings = Depends(get_settings),
    scheduler: DailyImprovementSchedulerService = Depends(get_daily_improvement_scheduler_service),
) -> DailyImprovementRunResponse:
    if settings.auth_enabled:
        caller_role = getattr(request.state, "api_role", "viewer")
        if caller_role not in {"admin", "operator"}:
            raise HTTPException(status_code=403, detail="Operator role required.")
    return DailyImprovementRunResponse(**scheduler.trigger_now())
