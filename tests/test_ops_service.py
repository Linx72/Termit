import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.core.api_key_config import ApiKeyConfig
from app.core.config import Settings
from app.services.ops_service import OpsService
from app.services.quota_store import QuotaStore


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
    )


class OpsServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_readiness_ready_with_auth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = build_settings(tmp)
            store = QuotaStore(settings.quota_sqlite_path)
            service = OpsService(settings=settings, quota_store=store)
            result = await service.readiness()
            self.assertIn(result.status, {"ready", "degraded"})
            self.assertGreater(result.passed, 5)
            names = {check.name for check in result.checks}
            self.assertIn("tool_safety", names)
            self.assertIn("rbac_boundaries", names)

    async def test_incident_drill_includes_recommendations_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = replace(build_settings(tmp, auth_enabled=False), auth_enabled=True, api_keys={})
            service = OpsService(settings=settings, quota_store=None)
            result = await service.incident_drill()
            self.assertEqual(result.status, "unhealthy")
            self.assertGreater(len(result.recommended_actions), 0)

    def test_mask_api_key(self) -> None:
        self.assertEqual(OpsService.mask_api_key("abcd"), "****")
        self.assertTrue(OpsService.mask_api_key("dev-key-1234").endswith("1234"))


class OpsApiTests(unittest.TestCase):
    def test_agent_run_ops_endpoints_available_without_auth(self) -> None:
        client = TestClient(app)
        metrics_resp = client.get("/api/ops/agent-runs/metrics")
        self.assertEqual(metrics_resp.status_code, 200)
        self.assertIn("queue_size", metrics_resp.json())

        cleanup_resp = client.post(
            "/api/ops/agent-runs/cleanup",
            json={"retention_days": 14, "dry_run": True},
        )
        self.assertEqual(cleanup_resp.status_code, 200)
        self.assertIn("deleted_runs", cleanup_resp.json())

        status_resp = client.get("/api/ops/agent-runs/maintenance")
        self.assertEqual(status_resp.status_code, 200)
        self.assertIn("enabled", status_resp.json())


if __name__ == "__main__":
    unittest.main()
