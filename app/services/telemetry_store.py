from __future__ import annotations

from pathlib import Path
from threading import Lock

from app.domain.schemas import MetricsSummaryResponse


class TelemetryStore:
    def __init__(self, max_latency_points: int = 5000, recent_window: int = 50) -> None:
        self._lock = Lock()
        self._max_latency_points = max(100, max_latency_points)
        self._recent_window = max(1, recent_window)
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
        self._http_latencies_ms: dict[str, list[int]] = {}
        self._http_requests_total: dict[str, int] = {}
        self._http_errors_total: dict[str, int] = {}

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

    def record_http_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        latency_ms: int,
    ) -> None:
        key = f"{method.upper()} {path}"
        with self._lock:
            self._http_requests_total[key] = self._http_requests_total.get(key, 0) + 1
            if status_code >= 400:
                self._http_errors_total[key] = self._http_errors_total.get(key, 0) + 1
            bucket = self._http_latencies_ms.setdefault(key, [])
            bucket.append(max(0, latency_ms))
            if len(bucket) > self._max_latency_points:
                self._http_latencies_ms[key] = bucket[-self._max_latency_points :]

    def http_endpoint_metrics(self) -> list[dict[str, object]]:
        with self._lock:
            rows: list[dict[str, object]] = []
            for key in sorted(self._http_requests_total.keys()):
                latencies = self._http_latencies_ms.get(key, [])
                rows.append(
                    {
                        "endpoint": key,
                        "requests_total": self._http_requests_total.get(key, 0),
                        "errors_total": self._http_errors_total.get(key, 0),
                        "latency_p95_ms": round(self._percentile(latencies, 95.0), 2),
                    }
                )
            return rows

    def hydrate_from_dev_seed(self, payload: dict[str, object]) -> bool:
        """Загрузить dev-only chat/task метрики из JSON (plan_status / cold start)."""
        if not payload.get("dev_only"):
            return False
        latencies_raw = payload.get("chat_latencies_ms")
        if not isinstance(latencies_raw, list) or not latencies_raw:
            return False
        latencies = [max(0, int(v)) for v in latencies_raw]
        with self._lock:
            self._chat_latencies_ms = latencies[-self._max_latency_points :]
            self._chat_requests_total = int(payload.get("chat_requests_total", len(latencies)) or len(latencies))
            self._chat_success_total = int(
                payload.get("chat_success_total", self._chat_requests_total) or self._chat_requests_total
            )
            self._chat_cache_hits_total = int(payload.get("chat_cache_hits_total", 0) or 0)
            self._chat_cache_miss_total = int(
                payload.get("chat_cache_miss_total", self._chat_requests_total) or self._chat_requests_total
            )
            self._task_total = int(payload.get("task_total", 0) or 0)
            self._task_completed = int(payload.get("task_completed", 0) or 0)
            self._task_failed = int(payload.get("task_failed", 0) or 0)
            self._task_auto_total = int(payload.get("task_auto_total", 0) or 0)
        return True

    @staticmethod
    def dev_seed_file_path(state_dir: str) -> Path:
        return Path(state_dir).resolve() / "dev_chat_metrics_seed.json"

    def snapshot(self) -> MetricsSummaryResponse:
        with self._lock:
            p50 = self._percentile(self._chat_latencies_ms, 50.0)
            p95 = self._percentile(self._chat_latencies_ms, 95.0)
            recent_latencies = self._chat_latencies_ms[-self._recent_window :]
            recent_p95 = self._percentile(recent_latencies, 95.0)
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
            cost_per_successful_task = (
                self._estimated_cost_total_usd / self._task_completed if self._task_completed else 0.0
            )
            return MetricsSummaryResponse(
                chat_requests_total=self._chat_requests_total,
                chat_success_total=self._chat_success_total,
                chat_cache_hits_total=self._chat_cache_hits_total,
                chat_cache_miss_total=self._chat_cache_miss_total,
                chat_success_rate=round(chat_success_rate, 4),
                chat_cache_hit_rate=round(chat_cache_hit_rate, 4),
                chat_latency_p50_ms=round(p50, 2),
                chat_latency_p95_ms=round(p95, 2),
                chat_latency_p95_recent_ms=round(recent_p95, 2),
                chat_recent_sample_size=len(recent_latencies),
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
                cost_per_successful_task_usd=round(cost_per_successful_task, 6),
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
