import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.api_key_config import ApiKeyConfig
from app.core.config import Settings
from app.domain.schemas import AgentAlertThresholds, AgentRunsMetricsResponse
from app.main import app
from app.services.alert_health_service import evaluate_agent_health, evaluate_chat_health
from app.services.ops_service import OpsService
from app.services.quota_store import QuotaStore
from app.domain.schemas import MetricsActiveThresholds, MetricsSummaryResponse


def build_settings(tmp_db: str, auth_enabled: bool = True) -> Settings:
    return Settings(
        host="0.0.0.0",
        port=8765,
        allowed_origins=["*"],
        default_model="ollama:default",
        code_model="ollama:code",
        analysis_model="ollama:analysis",
        default_fallback_model="openai_compat:default",
        code_fallback_model="openai_compat:code",
        analysis_fallback_model="openai_compat:analysis",
        ollama_base_url="http://localhost:11434",
        openai_compat_base_url="http://localhost:8001",
        openai_compat_api_key="",
        memory_backend="memory",
        memory_sqlite_path=str(Path(tmp_db) / "memory.db"),
        memory_max_messages=40,
        auth_enabled=auth_enabled,
        api_keys={
            "admin-key": ApiKeyConfig(daily_quota=100, role="admin", team="core"),
            "viewer-key": ApiKeyConfig(daily_quota=50, role="viewer", team="beta"),
        },
        quota_sqlite_path=str(Path(tmp_db) / "quota.db"),
        default_daily_quota=1000,
        default_api_role="operator",
        feedback_file_path=str(Path(tmp_db) / "feedback.jsonl"),
        circuit_failure_threshold=3,
        circuit_cooldown_seconds=60,
        eval_scenarios_path="./data/eval_scenarios.json",
        task_backend="memory",
        task_sqlite_path=str(Path(tmp_db) / "tasks.db"),
        agent_registry_file_path=str(Path(tmp_db) / "agents.json"),
        agent_run_sqlite_path=str(Path(tmp_db) / "agent_runs.db"),
        agent_alert_queue_utilization_percent=80.0,
        agent_alert_dead_letter_rate=0.15,
        agent_alert_min_worker_alive_ratio=1.0,
    )


class AlertHealthServiceTests(unittest.TestCase):
    def test_evaluate_chat_health_warning_near_threshold(self) -> None:
        summary = MetricsSummaryResponse(
            chat_requests_total=100,
            chat_success_total=95,
            chat_cache_hits_total=0,
            chat_cache_miss_total=100,
            chat_success_rate=0.95,
            chat_cache_hit_rate=0.0,
            chat_latency_p50_ms=100,
            chat_latency_p95_ms=200,
            chat_empty_response_rate=0.042,
            chat_fallback_rate=0.30,
            task_total=0,
            task_completed=0,
            task_failed=0,
            task_success_rate=0.0,
            automation_rate=0.0,
            estimated_cost_total_usd=0.0,
        )
        thresholds = MetricsActiveThresholds(
            degrade_empty_response_rate=0.05,
            degrade_fallback_rate=0.35,
        )
        status, reasons = evaluate_chat_health(summary, thresholds)
        self.assertEqual(status, "warning")
        self.assertTrue(any("near threshold" in item for item in reasons))

    def test_evaluate_chat_health_degraded_on_high_cost_per_success(self) -> None:
        summary = MetricsSummaryResponse(
            chat_requests_total=10,
            chat_success_total=10,
            chat_cache_hits_total=0,
            chat_cache_miss_total=10,
            chat_success_rate=1.0,
            chat_cache_hit_rate=0.0,
            chat_latency_p50_ms=100,
            chat_latency_p95_ms=200,
            task_total=5,
            task_completed=5,
            task_failed=0,
            task_success_rate=1.0,
            automation_rate=1.0,
            estimated_cost_total_usd=7.5,
            cost_per_successful_task_usd=1.5,
        )
        thresholds = MetricsActiveThresholds(max_cost_per_successful_task_usd=1.0)
        status, reasons = evaluate_chat_health(summary, thresholds)
        self.assertEqual(status, "degraded")
        self.assertTrue(any("Cost per successful task" in item for item in reasons))

    def test_evaluate_agent_health_degraded_on_queue_and_dead_letter(self) -> None:
        metrics = AgentRunsMetricsResponse(
            queue_size=85,
            queue_capacity=100,
            queue_utilization_percent=85.0,
            worker_count=2,
            alive_workers=2,
            total_runs=20,
            by_state={"completed": 8, "failed": 2, "queued": 85},
            active_runs=0,
        )
        thresholds = AgentAlertThresholds(
            queue_utilization_percent=80.0,
            dead_letter_rate=0.15,
            min_worker_alive_ratio=1.0,
            min_verify_pass_rate=0.70,
        )
        status, reasons, dead_letter_rate = evaluate_agent_health(metrics, thresholds)
        self.assertEqual(status, "degraded")
        self.assertGreaterEqual(dead_letter_rate, 0.15)
        self.assertTrue(any("queue utilization" in item.lower() for item in reasons))

    def test_evaluate_agent_health_degraded_on_low_verify_pass_rate(self) -> None:
        metrics = AgentRunsMetricsResponse(
            queue_size=1,
            queue_capacity=100,
            queue_utilization_percent=1.0,
            worker_count=2,
            alive_workers=2,
            total_runs=10,
            by_state={"completed": 10},
            active_runs=0,
            tool_loop_verify_pass_rate=0.55,
        )
        thresholds = AgentAlertThresholds(
            queue_utilization_percent=80.0,
            dead_letter_rate=0.15,
            min_worker_alive_ratio=1.0,
            min_verify_pass_rate=0.70,
        )
        status, reasons, _dead_letter_rate = evaluate_agent_health(metrics, thresholds)
        self.assertEqual(status, "degraded")
        self.assertTrue(any("verify pass rate" in item.lower() for item in reasons))


class HealthzApiTests(unittest.TestCase):
    def test_healthz_returns_dependency_breakdown(self) -> None:
        client = TestClient(app)
        response = client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(body["status"], {"ok", "degraded", "unhealthy"})
        self.assertIn("version", body)
        self.assertIn("dependencies", body)
        names = {item["name"] for item in body["dependencies"]}
        self.assertIn("memory_sqlite_writable", names)
        self.assertIn("agent_workers", names)
        self.assertIn("agent_maintenance", names)

    def test_metrics_thresholds_public(self) -> None:
        client = TestClient(app)
        response = client.get("/api/metrics/thresholds")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("chat", body)
        self.assertIn("agent", body)
        self.assertIn("degrade_empty_response_rate", body["chat"])
        self.assertIn("queue_utilization_percent", body["agent"])

    def test_agent_runs_metrics_include_health_fields(self) -> None:
        client = TestClient(app)
        response = client.get("/api/ops/agent-runs/metrics")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("health_status", body)
        self.assertIn("health_reasons", body)
        self.assertIn("dead_letter_rate", body)
        self.assertIn("active_thresholds", body)
        self.assertIn("tool_loop_runs", body)
        self.assertIn("tool_loop_tool_success_rate", body)
        self.assertIn("tool_loop_verify_passes", body)
        self.assertIn("tool_loop_verify_failures", body)
        self.assertIn("tool_loop_verify_retries", body)
        self.assertIn("tool_loop_verify_pass_rate", body)
        self.assertIn("orchestration_runs_total", body)
        self.assertIn("avg_coder_attempts", body)
        self.assertIn("coder_retry_success_rate", body)
        self.assertIn("openhands_contract_runs_total", body)
        self.assertIn("openhands_contract_actions_total", body)
        self.assertIn("orchestration_tool_loop_runs_total", body)
        self.assertIn("orchestration_tool_steps_total", body)
        self.assertIn("lifecycle_stale_total", body)
        self.assertIn("lifecycle_timeout_runs_total", body)
        self.assertIn("lifecycle_completion_rate", body)


class OpsServiceHealthzTests(unittest.IsolatedAsyncioTestCase):
    async def test_healthz_marks_missing_workers_unhealthy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = build_settings(tmp)
            service = OpsService(settings=settings, quota_store=QuotaStore(settings.quota_sqlite_path))
            result = await service.healthz(
                version="test",
                agent_workers_cb=lambda: {
                    "worker_count": 2,
                    "alive_workers": 0,
                },
                maintenance_status_cb=lambda: {"enabled": True, "thread_alive": True},
            )
            worker_dep = next(item for item in result.dependencies if item.name == "agent_workers")
            self.assertEqual(worker_dep.status, "unhealthy")
            self.assertEqual(result.status, "unhealthy")

    async def test_healthz_ok_when_dependencies_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = replace(build_settings(tmp), auth_enabled=False)
            service = OpsService(settings=settings, quota_store=None)
            result = await service.healthz(
                version="test",
                agent_workers_cb=lambda: {
                    "worker_count": 2,
                    "alive_workers": 2,
                },
                maintenance_status_cb=lambda: {"enabled": False},
            )
            self.assertIn(result.status, {"ok", "degraded"})


if __name__ == "__main__":
    unittest.main()
