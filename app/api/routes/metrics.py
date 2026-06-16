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
from app.services.alert_health_service import build_alert_thresholds_response, evaluate_agent_health, evaluate_chat_health
from app.services.metrics_snapshot_store import MetricsSnapshotStore
from app.services.telemetry_store import TelemetryStore
from app.services.agent_service import AgentService
from app.services.eval_service import EvalService
from app.services.multi_agent_orchestrator import MultiAgentOrchestrator
from app.state import (
    get_agent_service,
    get_eval_service,
    get_metrics_snapshot_store,
    get_multi_agent_orchestrator,
    get_telemetry_store,
)

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
            min_verify_pass_rate=settings.agent_alert_min_verify_pass_rate,
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
    orchestrator: MultiAgentOrchestrator = Depends(get_multi_agent_orchestrator),
    eval_service: EvalService = Depends(get_eval_service),
    settings: Settings = Depends(get_settings),
) -> PlainTextResponse:
    summary = telemetry.snapshot()
    queue = agent_service.queue_metrics()
    orchestration = orchestrator.metrics_snapshot()
    thresholds = AgentAlertThresholds(
        queue_utilization_percent=settings.agent_alert_queue_utilization_percent,
        dead_letter_rate=settings.agent_alert_dead_letter_rate,
        min_worker_alive_ratio=settings.agent_alert_min_worker_alive_ratio,
        min_verify_pass_rate=settings.agent_alert_min_verify_pass_rate,
    )
    _health_status, _health_reasons, dead_letter_rate = evaluate_agent_health(queue, thresholds)
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
        "# HELP termit_chat_fallback_rate Share of successful chats that used model fallback.",
        "# TYPE termit_chat_fallback_rate gauge",
        _prom_line("termit_chat_fallback_rate", float(summary.chat_fallback_rate)),
        "# HELP termit_chat_empty_response_rate Share of successful chats with empty body.",
        "# TYPE termit_chat_empty_response_rate gauge",
        _prom_line("termit_chat_empty_response_rate", float(summary.chat_empty_response_rate)),
        "# HELP termit_task_success_rate Completed tasks share.",
        "# TYPE termit_task_success_rate gauge",
        _prom_line("termit_task_success_rate", float(summary.task_success_rate)),
        "# HELP termit_cost_per_successful_task_usd Estimated USD per completed task.",
        "# TYPE termit_cost_per_successful_task_usd gauge",
        _prom_line("termit_cost_per_successful_task_usd", float(summary.cost_per_successful_task_usd)),
        "# HELP termit_estimated_cost_total_usd Estimated total model cost USD.",
        "# TYPE termit_estimated_cost_total_usd gauge",
        _prom_line("termit_estimated_cost_total_usd", float(summary.estimated_cost_total_usd)),
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
    lines.extend(
        [
            "# HELP termit_agent_active_runs Currently running agent runs.",
            "# TYPE termit_agent_active_runs gauge",
            _prom_line("termit_agent_active_runs", float(queue.get("active_runs", 0))),
            "# HELP termit_agent_stale_queued_runs Queued runs older than stuck timeout.",
            "# TYPE termit_agent_stale_queued_runs gauge",
            _prom_line("termit_agent_stale_queued_runs", float(queue.get("stale_queued_runs", 0))),
            "# HELP termit_agent_stale_running_runs Running runs older than stuck timeout.",
            "# TYPE termit_agent_stale_running_runs gauge",
            _prom_line("termit_agent_stale_running_runs", float(queue.get("stale_running_runs", 0))),
            "# HELP termit_agent_lifecycle_completion_rate Share of terminal runs completed successfully.",
            "# TYPE termit_agent_lifecycle_completion_rate gauge",
            _prom_line(
                "termit_agent_lifecycle_completion_rate",
                float(queue.get("lifecycle_completion_rate", 0.0)),
            ),
            "# HELP termit_agent_dead_letter_rate Failed runs share among terminal runs.",
            "# TYPE termit_agent_dead_letter_rate gauge",
            _prom_line("termit_agent_dead_letter_rate", float(dead_letter_rate)),
        ]
    )
    by_outcome = queue.get("by_outcome_class", {})
    if isinstance(by_outcome, dict) and by_outcome:
        lines.append("# HELP termit_agent_outcome_class_total Runs by outcome class.")
        lines.append("# TYPE termit_agent_outcome_class_total gauge")
        for outcome, count in sorted(by_outcome.items()):
            lines.append(
                _prom_line("termit_agent_outcome_class_total", int(count), labels={"outcome": str(outcome)})
            )
    for key, help_text in (
        ("tool_loop_runs", "Agent runs with tool-loop events."),
        ("tool_loop_tool_steps", "Successful tool-loop tool steps."),
        ("tool_loop_tool_errors", "Failed tool-loop tool steps."),
        ("tool_loop_parse_errors", "Tool-loop JSON parse errors."),
        ("tool_loop_final_steps", "Tool-loop final steps."),
        ("tool_loop_verify_passes", "Tool-loop verify pass events."),
        ("tool_loop_verify_failures", "Tool-loop verify failed events."),
        ("tool_loop_verify_retries", "Tool-loop verify retry scheduled events."),
    ):
        lines.append(f"# HELP termit_{key} {help_text}")
        lines.append(f"# TYPE termit_{key} gauge")
        lines.append(_prom_line(f"termit_{key}", float(queue.get(key, 0))))
    for key in ("tool_loop_tool_success_rate", "tool_loop_completion_rate", "tool_loop_verify_pass_rate"):
        lines.append(f"# HELP termit_{key} Tool-loop success ratio.")
        lines.append(f"# TYPE termit_{key} gauge")
        lines.append(_prom_line(f"termit_{key}", float(queue.get(key, 0.0))))
    for key, help_text in (
        ("orchestration_runs_total", "Total orchestration runs."),
        ("coder_attempts_total", "Total coder attempts in orchestration loop."),
        ("coder_retry_runs_total", "Orchestration runs requiring coder retry."),
        ("coder_retry_success_runs_total", "Runs where retry recovered reviewer feedback."),
        ("reviewer_reject_total", "Total reviewer reject outcomes."),
        ("openhands_contract_runs_total", "Runs with OpenHands-style contract enabled."),
        ("openhands_contract_actions_total", "Captured OpenHands action/observation pairs."),
        ("orchestration_tool_loop_runs_total", "Runs where orchestrator tool-loop executed."),
        ("orchestration_tool_steps_total", "Tool steps executed by orchestrator tool-loop."),
    ):
        lines.append(f"# HELP termit_{key} {help_text}")
        lines.append(f"# TYPE termit_{key} gauge")
        lines.append(_prom_line(f"termit_{key}", float(orchestration.get(key, 0.0))))
    for key, help_text in (
        ("avg_coder_attempts", "Average coder attempts per orchestration run."),
        ("coder_retry_run_rate", "Share of runs that required retry."),
        ("coder_retry_success_rate", "Retry success ratio among retried runs."),
    ):
        lines.append(f"# HELP termit_{key} {help_text}")
        lines.append(f"# TYPE termit_{key} gauge")
        lines.append(_prom_line(f"termit_{key}", float(orchestration.get(key, 0.0))))
    if summary.model_usage:
        lines.append("# HELP termit_model_usage_total Chat requests by model label.")
        lines.append("# TYPE termit_model_usage_total gauge")
        for model, count in sorted(summary.model_usage.items()):
            safe_model = str(model).replace('"', "")
            lines.append(
                _prom_line("termit_model_usage_total", int(count), labels={"model": safe_model})
            )
    eval_dashboard = eval_service.build_dashboard(report_limit=1)
    pass_by_category = eval_dashboard.get("pass_rate_by_category") or {}
    if isinstance(pass_by_category, dict) and pass_by_category:
        lines.append("# HELP termit_eval_pass_rate Eval pass rate from latest suite report.")
        lines.append("# TYPE termit_eval_pass_rate gauge")
        lines.append(
            _prom_line("termit_eval_pass_rate", float(eval_dashboard.get("pass_rate", 0.0)), labels={"scope": "overall"})
        )
        lines.append("# HELP termit_eval_pass_rate_by_category Pass rate by eval scenario category.")
        lines.append("# TYPE termit_eval_pass_rate_by_category gauge")
        for category, rate in sorted(pass_by_category.items()):
            safe_cat = str(category).replace('"', "")
            lines.append(
                _prom_line("termit_eval_pass_rate_by_category", float(rate), labels={"category": safe_cat})
            )
    for row in telemetry.http_endpoint_metrics():
        endpoint = str(row["endpoint"]).replace('"', "")
        labels = {"endpoint": endpoint}
        lines.append(_prom_line("termit_http_requests_total", int(row["requests_total"]), labels=labels))
        lines.append(_prom_line("termit_http_errors_total", int(row["errors_total"]), labels=labels))
        lines.append(_prom_line("termit_http_latency_p95_ms", float(row["latency_p95_ms"]), labels=labels))
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
