from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from app.core.config import Settings, get_settings
from app.domain.schemas import (
    AgentAlertThresholds,
    AlertThresholdsResponse,
    MetricsActiveThresholds,
    MetricsDailyReportResponse,
    MetricsExecutiveSummaryResponse,
    MetricsSlackPayloadResponse,
    MetricsSlackSummaryResponse,
    MetricsSnapshotResponse,
    MetricsSummaryResponse,
    MetricsTrendResponse,
)
from app.services.alert_health_service import build_alert_thresholds_response, evaluate_chat_health
from app.services.metrics_snapshot_store import MetricsSnapshotStore
from app.services.telemetry_store import TelemetryStore
from app.services.agent_service import AgentService
from app.state import get_agent_service, get_metrics_snapshot_store, get_telemetry_store

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics/thresholds", response_model=AlertThresholdsResponse)
async def metrics_thresholds(
    settings: Settings = Depends(get_settings),
) -> AlertThresholdsResponse:
    return build_alert_thresholds_response(
        chat=MetricsActiveThresholds(
            degrade_empty_response_rate=settings.degrade_empty_response_rate,
            degrade_fallback_rate=settings.degrade_fallback_rate,
        ),
        agent=AgentAlertThresholds(
            queue_utilization_percent=settings.agent_alert_queue_utilization_percent,
            dead_letter_rate=settings.agent_alert_dead_letter_rate,
            min_worker_alive_ratio=settings.agent_alert_min_worker_alive_ratio,
        ),
    )


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
    health_status, health_reasons = evaluate_chat_health(summary, thresholds)
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


def _prom_line(name: str, value: float, labels: Optional[dict[str, str]] = None) -> str:
    if labels:
        label_text = ",".join(f'{key}="{val}"' for key, val in sorted(labels.items()))
        return f"{name}{{{label_text}}} {value}"
    return f"{name} {value}"


@router.get("/metrics/http-endpoints")
async def metrics_http_endpoints(
    telemetry: TelemetryStore = Depends(get_telemetry_store),
) -> dict[str, object]:
    return {"endpoints": telemetry.http_endpoint_metrics()}


@router.get("/metrics/prometheus", response_class=PlainTextResponse)
async def metrics_prometheus(
    telemetry: TelemetryStore = Depends(get_telemetry_store),
    agent_service: AgentService = Depends(get_agent_service),
) -> PlainTextResponse:
    summary = telemetry.snapshot()
    queue = agent_service.queue_metrics()
    lines = [
        "# HELP termit_chat_requests_total Total chat requests.",
        "# TYPE termit_chat_requests_total counter",
        _prom_line("termit_chat_requests_total", summary.chat_requests_total),
        "# HELP termit_chat_success_total Total successful chat requests.",
        "# TYPE termit_chat_success_total counter",
        _prom_line("termit_chat_success_total", summary.chat_success_total),
        "# HELP termit_chat_latency_p95_ms Chat latency p95 in milliseconds.",
        "# TYPE termit_chat_latency_p95_ms gauge",
        _prom_line("termit_chat_latency_p95_ms", summary.chat_latency_p95_ms),
        "# HELP termit_agent_queue_size Current agent run queue depth.",
        "# TYPE termit_agent_queue_size gauge",
        _prom_line("termit_agent_queue_size", int(queue["queue_size"])),
        "# HELP termit_agent_queue_capacity Agent queue capacity.",
        "# TYPE termit_agent_queue_capacity gauge",
        _prom_line("termit_agent_queue_capacity", int(queue["queue_capacity"])),
        "# HELP termit_agent_queue_utilization_percent Queue utilization in percent.",
        "# TYPE termit_agent_queue_utilization_percent gauge",
        _prom_line("termit_agent_queue_utilization_percent", float(queue["queue_utilization_percent"])),
        "# HELP termit_agent_workers_configured Configured agent worker count.",
        "# TYPE termit_agent_workers_configured gauge",
        _prom_line("termit_agent_workers_configured", int(queue["worker_count"])),
        "# HELP termit_agent_workers_alive Alive agent worker count.",
        "# TYPE termit_agent_workers_alive gauge",
        _prom_line("termit_agent_workers_alive", int(queue.get("alive_workers", 0))),
    ]
    by_state = queue.get("by_state", {})
    if isinstance(by_state, dict):
        lines.append("# HELP termit_agent_runs_total Total runs by terminal state.")
        lines.append("# TYPE termit_agent_runs_total gauge")
        for state, count in sorted(by_state.items()):
            lines.append(_prom_line("termit_agent_runs_total", int(count), labels={"state": str(state)}))
    for row in telemetry.http_endpoint_metrics():
        endpoint = str(row["endpoint"]).replace('"', "")
        labels = {"endpoint": endpoint}
        lines.append(_prom_line("termit_http_requests_total", int(row["requests_total"]), labels=labels))
        lines.append(_prom_line("termit_http_errors_total", int(row["errors_total"]), labels=labels))
        lines.append(_prom_line("termit_http_latency_p95_ms", float(row["latency_p95_ms"]), labels=labels))
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
