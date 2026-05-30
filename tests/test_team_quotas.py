import tempfile
import unittest
from pathlib import Path

from app.core.api_key_config import ApiKeyConfig
from app.core.config import _parse_team_quotas
from app.services.quota_store import QuotaStore
from app.services.team_workspace_service import TeamWorkspaceService
from app.core.config import Settings


class TeamQuotaTests(unittest.TestCase):
    def test_parse_team_quotas(self) -> None:
        parsed = _parse_team_quotas("core:5000,beta:2000")
        self.assertEqual(parsed["core"], 5000)
        self.assertEqual(parsed["beta"], 2000)

    def test_consume_with_team_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = QuotaStore(str(Path(tmp) / "quota.db"))
            allowed, used, limit, team_used, team_limit = store.consume_with_team(
                "key-a",
                daily_limit=100,
                team="core",
                team_daily_limit=2,
            )
            self.assertTrue(allowed)
            self.assertEqual(used, 1)
            self.assertEqual(team_used, 1)
            self.assertEqual(team_limit, 2)

            allowed2, _, _, team_used2, _ = store.consume_with_team(
                "key-b",
                daily_limit=100,
                team="core",
                team_daily_limit=2,
            )
            self.assertTrue(allowed2)
            self.assertEqual(team_used2, 2)

            blocked, _, _, blocked_team_used, _ = store.consume_with_team(
                "key-c",
                daily_limit=100,
                team="core",
                team_daily_limit=2,
            )
            self.assertFalse(blocked)
            self.assertEqual(blocked_team_used, 2)

    def test_team_usage_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(
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
                memory_sqlite_path=str(Path(tmp) / "memory.db"),
                memory_max_messages=40,
                auth_enabled=True,
                api_keys={
                    "k1": ApiKeyConfig(daily_quota=50, role="operator", team="core"),
                    "k2": ApiKeyConfig(daily_quota=50, role="viewer", team="beta"),
                },
                quota_sqlite_path=str(Path(tmp) / "quota.db"),
                default_daily_quota=1000,
                default_api_role="operator",
                feedback_file_path=str(Path(tmp) / "feedback.jsonl"),
                circuit_failure_threshold=3,
                circuit_cooldown_seconds=60,
                eval_scenarios_path="./data/eval_scenarios.json",
                task_backend="memory",
                task_sqlite_path=str(Path(tmp) / "tasks.db"),
                team_quotas={"core": 10, "beta": 5},
            )
            store = QuotaStore(settings.quota_sqlite_path)
            store.consume_with_team("k1", 50, "core", 10)
            service = TeamWorkspaceService(settings, store)
            summary = service.team_usage(admin_view=True)
            self.assertEqual(len(summary.entries), 2)
            core_entry = next(item for item in summary.entries if item.team == "core")
            self.assertEqual(core_entry.used, 1)
            self.assertEqual(core_entry.limit, 10)


if __name__ == "__main__":
    unittest.main()
