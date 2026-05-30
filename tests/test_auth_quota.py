import tempfile
import unittest
from pathlib import Path

from app.core.auth import is_public_path
from app.core.api_key_config import ApiKeyConfig
from app.core.config import Settings, _parse_api_keys
from app.services.quota_store import QuotaStore
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.middleware.auth_quota import AuthQuotaMiddleware


class AuthHelpersTests(unittest.TestCase):
    def test_parse_api_keys_with_quota(self) -> None:
        from app.core.api_key_config import ApiKeyConfig

        parsed = _parse_api_keys("alpha:10,beta:20", default_daily_quota=100)
        self.assertEqual(parsed["alpha"], ApiKeyConfig(daily_quota=10, role="operator", team="default"))
        self.assertEqual(parsed["beta"], ApiKeyConfig(daily_quota=20, role="operator", team="default"))

    def test_public_paths(self) -> None:
        self.assertTrue(is_public_path("/health"))
        self.assertFalse(is_public_path("/api/chat"))


class QuotaStoreTests(unittest.TestCase):
    def test_consume_until_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = QuotaStore(str(Path(tmp) / "quota.db"))
            allowed1, used1, limit1 = store.consume("k1", daily_limit=2)
            allowed2, used2, limit2 = store.consume("k1", daily_limit=2)
            allowed3, used3, limit3 = store.consume("k1", daily_limit=2)

            self.assertTrue(allowed1)
            self.assertEqual(used1, 1)
            self.assertTrue(allowed2)
            self.assertEqual(used2, 2)
            self.assertFalse(allowed3)
            self.assertEqual(used3, 2)
            self.assertEqual(limit3, 2)


def _settings_for_auth() -> Settings:
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
        memory_sqlite_path="./test_memory.db",
        memory_max_messages=40,
        auth_enabled=True,
        api_keys={"test-key": ApiKeyConfig(daily_quota=1, role="admin")},
        quota_sqlite_path="./test_quota.db",
        default_daily_quota=1000,
        default_api_role="operator",
        feedback_file_path="./data/feedback.jsonl",
        circuit_failure_threshold=3,
        circuit_cooldown_seconds=60,
        eval_scenarios_path="./data/eval_scenarios.json",
        task_backend="memory",
        task_sqlite_path="./test_tasks.db",
        agent_registry_file_path="./data/agents.test.json",
    )


class AuthMiddlewareTests(unittest.TestCase):
    def test_blocks_missing_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings_for_auth()
            settings = Settings(
                **{
                    **settings.__dict__,
                    "quota_sqlite_path": str(Path(tmp) / "quota.db"),
                    "api_keys": {"test-key": ApiKeyConfig(daily_quota=5, role="admin")},
                }
            )
            store = QuotaStore(settings.quota_sqlite_path)
            app = FastAPI()

            @app.get("/api/ping")
            async def ping() -> dict[str, str]:
                return {"status": "ok"}

            app.add_middleware(AuthQuotaMiddleware, settings=settings, quota_store=store)
            client = TestClient(app)

            denied = client.get("/api/ping")
            self.assertEqual(denied.status_code, 401)

            allowed = client.get("/api/ping", headers={"X-API-Key": "test-key"})
            self.assertEqual(allowed.status_code, 200)

    def test_blocks_when_quota_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _settings_for_auth()
            settings = Settings(
                **{
                    **settings.__dict__,
                    "quota_sqlite_path": str(Path(tmp) / "quota.db"),
                    "api_keys": {"limited-key": ApiKeyConfig(daily_quota=1, role="admin")},
                }
            )
            store = QuotaStore(settings.quota_sqlite_path)
            app = FastAPI()

            @app.get("/api/ping")
            async def ping() -> dict[str, str]:
                return {"status": "ok"}

            app.add_middleware(AuthQuotaMiddleware, settings=settings, quota_store=store)
            client = TestClient(app)
            headers = {"X-API-Key": "limited-key"}

            first = client.get("/api/ping", headers=headers)
            second = client.get("/api/ping", headers=headers)

            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 429)


if __name__ == "__main__":
    unittest.main()
