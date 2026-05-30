from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

from app.domain.schemas import (
    MetricsDailyReportDelta,
    MetricsDailyReportResponse,
    MetricsExecutiveSummaryResponse,
    MetricsSlackPayloadResponse,
    MetricsSlackSummaryResponse,
    MetricsSnapshotResponse,
    MetricsSummaryResponse,
    MetricsTrendPoint,
    MetricsTrendResponse,
)


class MetricsSnapshotStore:
    DEGRADE_EMPTY_RESPONSE_RATE = 0.05
    DEGRADE_FALLBACK_RATE = 0.35
    ROLLING_WINDOW_POINTS = 3
    ROLLING_DEGRADE_RATIO = 2 / 3

    def __init__(
        self,
        file_path: str,
        degrade_empty_response_rate: float | None = None,
        degrade_fallback_rate: float | None = None,
    ) -> None:
        self.file_path = Path(file_path).resolve()
        self._lock = Lock()
        self._degrade_empty_response_rate = (
            self.DEGRADE_EMPTY_RESPONSE_RATE
            if degrade_empty_response_rate is None
            else max(0.0, min(1.0, degrade_empty_response_rate))
        )
        self._degrade_fallback_rate = (
            self.DEGRADE_FALLBACK_RATE
            if degrade_fallback_rate is None
            else max(0.0, min(1.0, degrade_fallback_rate))
        )
        self._last_slack_status: dict[str, str] = {}
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def append_snapshot(self, metrics: MetricsSummaryResponse) -> MetricsSnapshotResponse:
        snapshot = MetricsSnapshotResponse(
            captured_at=datetime.now(timezone.utc).isoformat(),
            metrics=metrics,
        )
        line = json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=True)
        with self._lock:
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return snapshot

    def trend(self, days: int = 7, limit: int = 200) -> MetricsTrendResponse:
        safe_days = max(1, min(days, 90))
        safe_limit = max(1, min(limit, 1000))
        cutoff = datetime.now(timezone.utc) - timedelta(days=safe_days)
        points: list[MetricsTrendPoint] = []

        if not self.file_path.exists():
            return MetricsTrendResponse(points=points)

        with self._lock:
            raw_lines = self.file_path.read_text(encoding="utf-8").splitlines()

        for line in raw_lines[-safe_limit:]:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                snapshot = MetricsSnapshotResponse.model_validate(payload)
            except Exception:  # noqa: BLE001
                continue
            captured_at = datetime.fromisoformat(snapshot.captured_at)
            if captured_at < cutoff:
                continue
            points.append(
                MetricsTrendPoint(
                    captured_at=snapshot.captured_at,
                    chat_success_rate=snapshot.metrics.chat_success_rate,
                    chat_cache_hit_rate=snapshot.metrics.chat_cache_hit_rate,
                    chat_latency_p95_ms=snapshot.metrics.chat_latency_p95_ms,
                    chat_empty_response_rate=snapshot.metrics.chat_empty_response_rate,
                    chat_fallback_rate=snapshot.metrics.chat_fallback_rate,
                    task_success_rate=snapshot.metrics.task_success_rate,
                    automation_rate=snapshot.metrics.automation_rate,
                    estimated_cost_total_usd=snapshot.metrics.estimated_cost_total_usd,
                )
            )
        points.sort(key=lambda point: point.captured_at)
        return MetricsTrendResponse(points=points)

    def daily_report(self, days: int = 7, limit: int = 200) -> MetricsDailyReportResponse:
        trend = self.trend(days=days, limit=limit)
        points = trend.points
        if not points:
            return MetricsDailyReportResponse(period_days=days, points_count=0)
        latest = points[-1]
        if len(points) == 1:
            return MetricsDailyReportResponse(
                period_days=days,
                points_count=1,
                latest=latest,
            )
        previous = points[-2]
        delta = MetricsDailyReportDelta(
            chat_success_rate_delta=round(latest.chat_success_rate - previous.chat_success_rate, 4),
            chat_cache_hit_rate_delta=round(latest.chat_cache_hit_rate - previous.chat_cache_hit_rate, 4),
            chat_latency_p95_ms_delta=round(latest.chat_latency_p95_ms - previous.chat_latency_p95_ms, 2),
            task_success_rate_delta=round(latest.task_success_rate - previous.task_success_rate, 4),
            automation_rate_delta=round(latest.automation_rate - previous.automation_rate, 4),
            estimated_cost_total_usd_delta=round(
                latest.estimated_cost_total_usd - previous.estimated_cost_total_usd,
                6,
            ),
        )
        return MetricsDailyReportResponse(
            period_days=days,
            points_count=len(points),
            latest=latest,
            previous=previous,
            delta=delta,
        )

    def executive_summary(self, days: int = 7, limit: int = 200) -> MetricsExecutiveSummaryResponse:
        trend = self.trend(days=days, limit=limit)
        trend_points = trend.points
        report = self.daily_report(days=days, limit=limit)
        if report.points_count == 0:
            return MetricsExecutiveSummaryResponse(
                period_days=days,
                points_count=0,
                status="insufficient_data",
                highlights=["No KPI snapshots available yet."],
            )
        if report.points_count == 1 or report.delta is None:
            return MetricsExecutiveSummaryResponse(
                period_days=days,
                points_count=report.points_count,
                status="insufficient_data",
                latest=report.latest,
                previous=report.previous,
                highlights=["Only one snapshot available; collect at least two for trend deltas."],
            )

        improvements: list[str] = []
        regressions: list[str] = []
        delta = report.delta

        if delta.chat_success_rate_delta >= 0.01:
            improvements.append(f"Chat success rate improved by {delta.chat_success_rate_delta:+.2%}.")
        elif delta.chat_success_rate_delta <= -0.01:
            regressions.append(f"Chat success rate dropped by {delta.chat_success_rate_delta:+.2%}.")

        if delta.chat_cache_hit_rate_delta >= 0.05:
            improvements.append(f"Cache hit rate improved by {delta.chat_cache_hit_rate_delta:+.2%}.")
        elif delta.chat_cache_hit_rate_delta <= -0.05:
            regressions.append(f"Cache hit rate dropped by {delta.chat_cache_hit_rate_delta:+.2%}.")

        if delta.chat_latency_p95_ms_delta <= -50:
            improvements.append(
                f"p95 latency improved by {abs(delta.chat_latency_p95_ms_delta):.0f} ms."
            )
        elif delta.chat_latency_p95_ms_delta >= 50:
            regressions.append(f"p95 latency regressed by {delta.chat_latency_p95_ms_delta:.0f} ms.")

        if delta.task_success_rate_delta >= 0.01:
            improvements.append(f"Task success rate improved by {delta.task_success_rate_delta:+.2%}.")
        elif delta.task_success_rate_delta <= -0.01:
            regressions.append(f"Task success rate dropped by {delta.task_success_rate_delta:+.2%}.")

        if delta.automation_rate_delta >= 0.02:
            improvements.append(f"Automation rate improved by {delta.automation_rate_delta:+.2%}.")
        elif delta.automation_rate_delta <= -0.02:
            regressions.append(f"Automation rate dropped by {delta.automation_rate_delta:+.2%}.")

        if delta.estimated_cost_total_usd_delta <= -0.001:
            improvements.append(
                f"Estimated total cost decreased by ${abs(delta.estimated_cost_total_usd_delta):.4f}."
            )
        elif delta.estimated_cost_total_usd_delta >= 0.001:
            regressions.append(
                f"Estimated total cost increased by ${delta.estimated_cost_total_usd_delta:.4f}."
            )

        if regressions and not improvements:
            status = "regressing"
        elif improvements and not regressions:
            status = "improving"
        elif improvements and regressions:
            status = "mixed"
        else:
            status = "stable"

        if report.latest is not None:
            if report.latest.chat_empty_response_rate >= self._degrade_empty_response_rate:
                regressions.append(
                    "High empty response rate: "
                    f"{report.latest.chat_empty_response_rate:.2%} "
                    f"(threshold {self._degrade_empty_response_rate:.0%})."
                )
                status = "degraded"

        if len(trend_points) >= 2:
            window = trend_points[-min(len(trend_points), self.ROLLING_WINDOW_POINTS) :]
            empty_breaches = sum(
                1 for point in window if point.chat_empty_response_rate >= self._degrade_empty_response_rate
            )
            fallback_breaches = sum(
                1 for point in window if point.chat_fallback_rate >= self._degrade_fallback_rate
            )
            window_size = len(window)
            required = max(1, math.ceil(self.ROLLING_DEGRADE_RATIO * window_size))
            if empty_breaches >= required:
                regressions.append(
                    "Rolling window degradation: empty response threshold breached "
                    f"in {empty_breaches}/{window_size} latest snapshots."
                )
                status = "degraded"
            if fallback_breaches >= required:
                regressions.append(
                    "Rolling window degradation: fallback threshold breached "
                    f"in {fallback_breaches}/{window_size} latest snapshots."
                )
                status = "degraded"
            if report.latest.chat_fallback_rate >= self._degrade_fallback_rate:
                regressions.append(
                    "High fallback usage rate: "
                    f"{report.latest.chat_fallback_rate:.2%} "
                    f"(threshold {self._degrade_fallback_rate:.0%})."
                )
                status = "degraded"

        highlights = [
            f"Status: {status}.",
            f"Points analyzed: {report.points_count} over {days} day(s).",
        ]
        if report.latest:
            highlights.append(
                "Latest KPI snapshot: "
                f"success={report.latest.chat_success_rate:.2%}, "
                f"task_success={report.latest.task_success_rate:.2%}, "
                f"p95={report.latest.chat_latency_p95_ms:.0f} ms."
            )

        return MetricsExecutiveSummaryResponse(
            period_days=days,
            points_count=report.points_count,
            status=status,
            improvements=improvements,
            regressions=regressions,
            highlights=highlights,
            latest=report.latest,
            previous=report.previous,
        )

    def slack_summary(self, days: int = 7, limit: int = 200) -> MetricsSlackSummaryResponse:
        summary = self.executive_summary(days=days, limit=limit)
        bullets: list[str] = []
        bullets.extend(summary.improvements[:3])
        bullets.extend(summary.regressions[:3])
        if not bullets:
            bullets.extend(summary.highlights[:3])

        header = (
            f"*Termit KPI ({days}d)* - status: *{summary.status}* | "
            f"points: {summary.points_count}"
        )
        body = "\n".join(f"- {item}" for item in bullets)
        text = header if not body else f"{header}\n{body}"
        return MetricsSlackSummaryResponse(
            status=summary.status,
            text=text,
            bullet_count=len(bullets),
        )

    def slack_payload(self, days: int = 7, limit: int = 200) -> MetricsSlackPayloadResponse:
        summary = self.slack_summary(days=days, limit=limit)
        key = f"{days}:{limit}"
        with self._lock:
            previous_status = self._last_slack_status.get(key)
            should_notify = previous_status != summary.status
            if should_notify:
                self._last_slack_status[key] = summary.status
        payload: dict[str, object] = {
            "text": summary.text,
            "mrkdwn": True,
            "unfurl_links": False,
            "unfurl_media": False,
        }
        if not should_notify:
            payload = {
                "text": f"No status change (still {summary.status}).",
                "mrkdwn": False,
                "unfurl_links": False,
                "unfurl_media": False,
            }
        return MetricsSlackPayloadResponse(
            status=summary.status,
            should_notify=should_notify,
            previous_status=previous_status,
            payload=payload,
        )
