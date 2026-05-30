from __future__ import annotations

from threading import Lock

from app.domain.schemas import MetricsSummaryResponse


class TelemetryStore:
    def __init__(self, max_latency_points: int = 5000) -> None:
        self._lock = Lock()
        self._max_latency_points = max(100, max_latency_points)
        self._chat_requests_total = 0
        self._chat_success_total = 0
        self._chat_cache_hits_total = 0
        self._chat_cache_miss_total = 0
        self._chat_latencies_ms: list[int] = []
        self._chat_empty_response_total = 0
        self._chat_code_response_total = 0
        self._chat_fallback_used_total = 0
        self._chat_response_chars_total = 0
        self._task_total = 0
        self._task_completed = 0
        self._task_failed = 0
        self._task_auto_total = 0
        self._estimated_cost_total_usd = 0.0
        self._model_usage: dict[str, int] = {}
        self._failure_classes: dict[str, int] = {}

    def record_chat(
        self,
        *,
        success: bool,
        cache_hit: bool,
        latency_ms: int,
        selected_model: str | None,
        estimated_cost_usd: float,
        response_text: str,
        fallback_used: bool,
    ) -> None:
        with self._lock:
            self._chat_requests_total += 1
            if success:
                self._chat_success_total += 1
            if cache_hit:
                self._chat_cache_hits_total += 1
            else:
                self._chat_cache_miss_total += 1
            self._chat_latencies_ms.append(max(0, latency_ms))
            if len(self._chat_latencies_ms) > self._max_latency_points:
                self._chat_latencies_ms = self._chat_latencies_ms[-self._max_latency_points :]
            self._estimated_cost_total_usd += max(0.0, estimated_cost_usd)
            if selected_model:
                self._model_usage[selected_model] = self._model_usage.get(selected_model, 0) + 1
            if success:
                response_chars = len(response_text)
                self._chat_response_chars_total += response_chars
                if not response_text.strip():
                    self._chat_empty_response_total += 1
                if "```" in response_text:
                    self._chat_code_response_total += 1
                if fallback_used:
                    self._chat_fallback_used_total += 1

    def record_task(self, *, completed: bool, auto_mode: bool, failure_class: str | None) -> None:
        with self._lock:
            self._task_total += 1
            if auto_mode:
                self._task_auto_total += 1
            if completed:
                self._task_completed += 1
            else:
                self._task_failed += 1
            if failure_class:
                self._failure_classes[failure_class] = self._failure_classes.get(failure_class, 0) + 1

    def snapshot(self) -> MetricsSummaryResponse:
        with self._lock:
            p50 = self._percentile(self._chat_latencies_ms, 50.0)
            p95 = self._percentile(self._chat_latencies_ms, 95.0)
            chat_success_rate = (
                self._chat_success_total / self._chat_requests_total
                if self._chat_requests_total
                else 0.0
            )
            chat_cache_hit_rate = (
                self._chat_cache_hits_total / self._chat_requests_total
                if self._chat_requests_total
                else 0.0
            )
            quality_denominator = self._chat_success_total if self._chat_success_total else 1
            avg_response_chars = self._chat_response_chars_total / quality_denominator
            empty_rate = self._chat_empty_response_total / quality_denominator
            code_rate = self._chat_code_response_total / quality_denominator
            fallback_rate = self._chat_fallback_used_total / quality_denominator
            task_success_rate = (
                self._task_completed / self._task_total if self._task_total else 0.0
            )
            automation_rate = self._task_auto_total / self._task_total if self._task_total else 0.0
            return MetricsSummaryResponse(
                chat_requests_total=self._chat_requests_total,
                chat_success_total=self._chat_success_total,
                chat_cache_hits_total=self._chat_cache_hits_total,
                chat_cache_miss_total=self._chat_cache_miss_total,
                chat_success_rate=round(chat_success_rate, 4),
                chat_cache_hit_rate=round(chat_cache_hit_rate, 4),
                chat_latency_p50_ms=round(p50, 2),
                chat_latency_p95_ms=round(p95, 2),
                chat_empty_response_total=self._chat_empty_response_total,
                chat_code_response_total=self._chat_code_response_total,
                chat_fallback_used_total=self._chat_fallback_used_total,
                chat_avg_response_chars=round(avg_response_chars, 2),
                chat_empty_response_rate=round(empty_rate, 4),
                chat_code_response_rate=round(code_rate, 4),
                chat_fallback_rate=round(fallback_rate, 4),
                task_total=self._task_total,
                task_completed=self._task_completed,
                task_failed=self._task_failed,
                task_success_rate=round(task_success_rate, 4),
                automation_rate=round(automation_rate, 4),
                estimated_cost_total_usd=round(self._estimated_cost_total_usd, 6),
                model_usage=dict(self._model_usage),
                failure_classes=dict(self._failure_classes),
            )

    @staticmethod
    def _percentile(values: list[int], percentile: float) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        rank = (percentile / 100.0) * (len(sorted_values) - 1)
        lower = int(rank)
        upper = min(lower + 1, len(sorted_values) - 1)
        weight = rank - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
