from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import Settings, get_settings
from app.domain.schemas import (
    AgentAlertThresholds,
    AgentRunsCleanupRequest,
    AgentRunsCleanupResponse,
    AgentRunsMetricsResponse,
    OpsIncidentDrillResponse,
    OpsReadinessResponse,
    QuotaResetRequest,
    QuotaResetResponse,
    QuotaSummaryResponse,
    QuotaEntrySummary,
)
from app.services.alert_health_service import evaluate_agent_health
from app.services.ops_service import OpsService
from app.services.agent_service import AgentService
from app.services.agent_maintenance_scheduler_service import AgentMaintenanceSchedulerService
from app.services.quota_store import QuotaStore
from app.state import (
    get_agent_maintenance_scheduler_service,
    get_agent_service,
    get_chat_service,
    get_ops_service,
    get_quota_store,
)

router = APIRouter(prefix="/api/ops", tags=["ops"])


def _agent_runs_metrics_payload(
    service: AgentService,
    settings: Settings,
) -> AgentRunsMetricsResponse:
    raw = service.queue_metrics()
    thresholds = AgentAlertThresholds(
        queue_utilization_percent=settings.agent_alert_queue_utilization_percent,
        dead_letter_rate=settings.agent_alert_dead_letter_rate,
        min_worker_alive_ratio=settings.agent_alert_min_worker_alive_ratio,
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
) -> OpsReadinessResponse:
    chat = get_chat_service()
    return await ops.readiness(providers_status_cb=chat.providers_status)


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
) -> AgentRunsMetricsResponse:
    return _agent_runs_metrics_payload(service, settings)


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
) -> dict[str, object]:
    from app.state import get_alert_webhook_service

    if settings.auth_enabled:
        caller_role = getattr(request.state, "api_role", "viewer")
        if caller_role not in {"admin", "operator"}:
            raise HTTPException(status_code=403, detail="Operator role required.")

    metrics = _agent_runs_metrics_payload(agent_service, settings)
    webhook = get_alert_webhook_service()
    if not webhook.enabled:
        return {"sent": False, "reason": "webhook_not_configured", "health_status": metrics.health_status}

    detail = "; ".join(metrics.health_reasons) if metrics.health_reasons else "All checks passed."
    result = webhook.send(
        title="Termit agent ops alert",
        status=str(metrics.health_status),
        detail=detail,
        payload={"dead_letter_rate": metrics.dead_letter_rate},
    )
    return {"health_status": metrics.health_status, **result}
