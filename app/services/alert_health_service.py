from __future__ import annotations

from app.domain.schemas import (
    AgentAlertThresholds,
    AgentRunsMetricsResponse,
    AlertThresholdsResponse,
    MetricsActiveThresholds,
    MetricsSummaryResponse,
)


def evaluate_chat_health(
    summary: MetricsSummaryResponse,
    thresholds: MetricsActiveThresholds,
) -> tuple[str, list[str]]:
    warning_reasons: list[str] = []
    degraded_reasons: list[str] = []
    empty_rate = summary.chat_empty_response_rate
    fallback_rate = summary.chat_fallback_rate

    if empty_rate >= thresholds.degrade_empty_response_rate:
        degraded_reasons.append(
            f"Empty response rate is {empty_rate:.2%} "
            f"(threshold {thresholds.degrade_empty_response_rate:.2%})."
        )
    elif empty_rate >= thresholds.degrade_empty_response_rate * 0.8:
        warning_reasons.append(
            f"Empty response rate is near threshold: "
            f"{empty_rate:.2%}/{thresholds.degrade_empty_response_rate:.2%}."
        )

    if fallback_rate >= thresholds.degrade_fallback_rate:
        degraded_reasons.append(
            f"Fallback rate is {fallback_rate:.2%} "
            f"(threshold {thresholds.degrade_fallback_rate:.2%})."
        )
    elif fallback_rate >= thresholds.degrade_fallback_rate * 0.8:
        warning_reasons.append(
            f"Fallback rate is near threshold: "
            f"{fallback_rate:.2%}/{thresholds.degrade_fallback_rate:.2%}."
        )

    cost_per_success = float(summary.cost_per_successful_task_usd or 0.0)
    max_cost = float(thresholds.max_cost_per_successful_task_usd or 0.0)
    if max_cost > 0 and summary.task_completed > 0 and cost_per_success > max_cost:
        degraded_reasons.append(
            f"Cost per successful task is ${cost_per_success:.4f} "
            f"(threshold ${max_cost:.4f})."
        )
    elif max_cost > 0 and summary.task_completed > 0 and cost_per_success > max_cost * 0.8:
        warning_reasons.append(
            f"Cost per successful task is near threshold: "
            f"${cost_per_success:.4f}/${max_cost:.4f}."
        )

    if degraded_reasons:
        return "degraded", degraded_reasons
    if warning_reasons:
        return "warning", warning_reasons
    return "ok", []


def evaluate_agent_health(
    metrics: AgentRunsMetricsResponse | dict[str, object],
    thresholds: AgentAlertThresholds,
) -> tuple[str, list[str], float]:
    if isinstance(metrics, AgentRunsMetricsResponse):
        queue_util = metrics.queue_utilization_percent
        worker_count = metrics.worker_count
        alive_workers = metrics.alive_workers
        by_state = metrics.by_state
        total_runs = metrics.total_runs
        verify_pass_rate = metrics.tool_loop_verify_pass_rate
    else:
        queue_util = float(metrics.get("queue_utilization_percent", 0))
        worker_count = int(metrics.get("worker_count", 0))
        alive_workers = int(metrics.get("alive_workers", 0))
        by_state = metrics.get("by_state", {})
        total_runs = int(metrics.get("total_runs", 0))
        verify_pass_rate = float(metrics.get("tool_loop_verify_pass_rate", 0.0))

    warning_reasons: list[str] = []
    degraded_reasons: list[str] = []
    failed_count = 0
    if isinstance(by_state, dict):
        failed_count = int(by_state.get("failed", 0))

    # Dead-letter denominator: считаем только completed + failed
    # (cancelled — действия пользователя, не исходы системы)
    completed_count = 0
    if isinstance(by_state, dict):
        completed_count = int(by_state.get("completed", 0))
    terminal_for_dl = failed_count + completed_count
    dead_letter_rate = failed_count / max(1, terminal_for_dl)
    worker_ratio = alive_workers / max(1, worker_count)

    if queue_util >= thresholds.queue_utilization_percent:
        degraded_reasons.append(
            f"Agent queue utilization is {queue_util:.1f}% "
            f"(threshold {thresholds.queue_utilization_percent:.1f}%)."
        )
    elif queue_util >= thresholds.queue_utilization_percent * 0.8:
        warning_reasons.append(
            f"Agent queue utilization is near threshold: "
            f"{queue_util:.1f}%/{thresholds.queue_utilization_percent:.1f}%."
        )

    if dead_letter_rate >= thresholds.dead_letter_rate:
        degraded_reasons.append(
            f"Dead-letter rate is {dead_letter_rate:.2%} "
            f"(threshold {thresholds.dead_letter_rate:.2%}, failed={failed_count})."
        )
    elif dead_letter_rate >= thresholds.dead_letter_rate * 0.8:
        warning_reasons.append(
            f"Dead-letter rate is near threshold: "
            f"{dead_letter_rate:.2%}/{thresholds.dead_letter_rate:.2%}."
        )

    if worker_ratio < thresholds.min_worker_alive_ratio:
        if alive_workers == 0:
            degraded_reasons.append(
                f"No agent workers alive (configured={worker_count})."
            )
        else:
            degraded_reasons.append(
                f"Agent worker availability is {worker_ratio:.0%} "
                f"(threshold {thresholds.min_worker_alive_ratio:.0%}, "
                f"alive={alive_workers}/{worker_count})."
            )
    elif worker_ratio < 1.0:
        warning_reasons.append(
            f"Some agent workers are down ({alive_workers}/{worker_count} alive)."
        )

    if verify_pass_rate < thresholds.min_verify_pass_rate:
        degraded_reasons.append(
            f"Tool-loop verify pass rate is {verify_pass_rate:.2%} "
            f"(threshold {thresholds.min_verify_pass_rate:.2%})."
        )
    elif verify_pass_rate < min(1.0, thresholds.min_verify_pass_rate + 0.10):
        warning_reasons.append(
            f"Tool-loop verify pass rate is near threshold: "
            f"{verify_pass_rate:.2%}/{thresholds.min_verify_pass_rate:.2%}."
        )

    if total_runs == 0 and not degraded_reasons and not warning_reasons:
        warning_reasons.append("No agent runs recorded yet.")

    if degraded_reasons:
        return "degraded", degraded_reasons, dead_letter_rate
    if warning_reasons:
        return "warning", warning_reasons, dead_letter_rate
    return "ok", [], dead_letter_rate


def build_alert_thresholds_response(
    chat: MetricsActiveThresholds,
    agent: AgentAlertThresholds,
) -> AlertThresholdsResponse:
    return AlertThresholdsResponse(chat=chat, agent=agent)
