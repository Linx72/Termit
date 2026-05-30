from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.domain.schemas import (
    MetricsActiveThresholds,
    MetricsDailyReportResponse,
    MetricsExecutiveSummaryResponse,
    MetricsSlackPayloadResponse,
    MetricsSlackSummaryResponse,
    MetricsSnapshotResponse,
    MetricsSummaryResponse,
    MetricsTrendResponse,
)
from app.services.metrics_snapshot_store import MetricsSnapshotStore
from app.services.telemetry_store import TelemetryStore
from app.state import get_metrics_snapshot_store, get_telemetry_store

router = APIRouter(prefix="/api", tags=["metrics"])


def _health_from_summary(
    summary: MetricsSummaryResponse, thresholds: MetricsActiveThresholds
) -> tuple[str, list[str]]:
    warning_reasons: list[str] = []
    degraded_reasons: list[str] = []
    empty_rate = summary.chat_empty_response_rate
    fallback_rate = summary.chat_fallback_rate

    if empty_rate >= thresholds.degrade_empty_response_rate:
        degraded_reasons.append(
            f"Empty response rate is {empty_rate:.2%} (threshold {thresholds.degrade_empty_response_rate:.2%})."
        )
    elif empty_rate >= thresholds.degrade_empty_response_rate * 0.8:
        warning_reasons.append(
            f"Empty response rate is near threshold: {empty_rate:.2%}/{thresholds.degrade_empty_response_rate:.2%}."
        )

    if fallback_rate >= thresholds.degrade_fallback_rate:
        degraded_reasons.append(
            f"Fallback rate is {fallback_rate:.2%} (threshold {thresholds.degrade_fallback_rate:.2%})."
        )
    elif fallback_rate >= thresholds.degrade_fallback_rate * 0.8:
        warning_reasons.append(
            f"Fallback rate is near threshold: {fallback_rate:.2%}/{thresholds.degrade_fallback_rate:.2%}."
        )

    if degraded_reasons:
        return "degraded", degraded_reasons
    if warning_reasons:
        return "warning", warning_reasons
    return "ok", []


@router.get("/metrics", response_model=MetricsSummaryResponse)
async def metrics_summary(
    telemetry: TelemetryStore = Depends(get_telemetry_store),
    settings: Settings = Depends(get_settings),
) -> MetricsSummaryResponse:
    thresholds = MetricsActiveThresholds(
        degrade_empty_response_rate=settings.degrade_empty_response_rate,
        degrade_fallback_rate=settings.degrade_fallback_rate,
    )
    summary = telemetry.snapshot()
    health_status, health_reasons = _health_from_summary(summary, thresholds)
    return summary.model_copy(
        update={
            "active_thresholds": thresholds,
            "health_status": health_status,
            "health_reasons": health_reasons,
        }
    )


@router.post("/metrics/snapshot", response_model=MetricsSnapshotResponse)
async def capture_metrics_snapshot(
    telemetry: TelemetryStore = Depends(get_telemetry_store),
    snapshots: MetricsSnapshotStore = Depends(get_metrics_snapshot_store),
) -> MetricsSnapshotResponse:
    return snapshots.append_snapshot(telemetry.snapshot())


@router.get("/metrics/trend", response_model=MetricsTrendResponse)
async def metrics_trend(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=200, ge=1, le=1000),
    snapshots: MetricsSnapshotStore = Depends(get_metrics_snapshot_store),
) -> MetricsTrendResponse:
    return snapshots.trend(days=days, limit=limit)


@router.get("/metrics/daily-report", response_model=MetricsDailyReportResponse)
async def metrics_daily_report(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=200, ge=1, le=1000),
    snapshots: MetricsSnapshotStore = Depends(get_metrics_snapshot_store),
) -> MetricsDailyReportResponse:
    return snapshots.daily_report(days=days, limit=limit)


@router.get("/metrics/executive-summary", response_model=MetricsExecutiveSummaryResponse)
async def metrics_executive_summary(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=200, ge=1, le=1000),
    snapshots: MetricsSnapshotStore = Depends(get_metrics_snapshot_store),
) -> MetricsExecutiveSummaryResponse:
    return snapshots.executive_summary(days=days, limit=limit)


@router.get("/metrics/executive-summary/slack", response_model=MetricsSlackSummaryResponse)
async def metrics_executive_summary_slack(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=200, ge=1, le=1000),
    snapshots: MetricsSnapshotStore = Depends(get_metrics_snapshot_store),
) -> MetricsSlackSummaryResponse:
    return snapshots.slack_summary(days=days, limit=limit)


@router.get("/metrics/executive-summary/slack/payload", response_model=MetricsSlackPayloadResponse)
async def metrics_executive_summary_slack_payload(
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=200, ge=1, le=1000),
    snapshots: MetricsSnapshotStore = Depends(get_metrics_snapshot_store),
) -> MetricsSlackPayloadResponse:
    return snapshots.slack_payload(days=days, limit=limit)
