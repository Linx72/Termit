import tempfile
import unittest
from pathlib import Path

from app.core.api_key_config import ApiKeyConfig
from app.core.config import _parse_api_keys
from app.core.rbac import role_allows, required_role
from app.services.eval_service import EvalService
from app.services.feedback_store import FeedbackStore
from app.services.provider_circuit_breaker import ProviderCircuitBreaker


class RbacTests(unittest.TestCase):
    def test_viewer_cannot_execute_command(self) -> None:
        self.assertFalse(role_allows("viewer", "POST", "/api/tools/execute_command"))

    def test_operator_can_execute_command(self) -> None:
        self.assertTrue(role_allows("operator", "POST", "/api/tools/execute_command"))

    def test_viewer_cannot_apply_patch(self) -> None:
        self.assertFalse(role_allows("viewer", "POST", "/api/tools/apply_patch"))

    def test_operator_can_apply_patch(self) -> None:
        self.assertTrue(role_allows("operator", "POST", "/api/tools/apply_patch"))

    def test_admin_required_for_session_delete(self) -> None:
        self.assertEqual(required_role("DELETE", "/api/sessions/abc"), "admin")

    def test_admin_required_for_incident_drill(self) -> None:
        self.assertEqual(required_role("POST", "/api/ops/incident-drill"), "admin")

    def test_viewer_can_read_ops_readiness(self) -> None:
        self.assertTrue(role_allows("viewer", "GET", "/api/ops/readiness"))

    def test_viewer_can_read_agent_run_metrics(self) -> None:
        self.assertEqual(required_role("GET", "/api/ops/agent-runs/metrics"), "viewer")
        self.assertTrue(role_allows("viewer", "GET", "/api/ops/agent-runs/metrics"))
        self.assertTrue(role_allows("operator", "GET", "/api/ops/agent-runs/metrics"))

    def test_admin_required_for_agent_run_mutations(self) -> None:
        self.assertEqual(required_role("POST", "/api/ops/agent-runs/cleanup"), "admin")


class PlatformServicesTests(unittest.TestCase):
    def test_parse_api_keys_with_role(self) -> None:
        parsed = _parse_api_keys("alpha:10:viewer,beta:20:admin", 100, default_role="operator")
        self.assertEqual(parsed["alpha"], ApiKeyConfig(daily_quota=10, role="viewer", team="default"))
        self.assertEqual(parsed["beta"], ApiKeyConfig(daily_quota=20, role="admin", team="default"))

    def test_circuit_breaker_opens_after_failures(self) -> None:
        breaker = ProviderCircuitBreaker(failure_threshold=2, cooldown_seconds=60)
        breaker.record_failure("ollama")
        self.assertTrue(breaker.is_available("ollama"))
        breaker.record_failure("ollama")
        self.assertFalse(breaker.is_available("ollama"))

    def test_feedback_store_appends(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FeedbackStore(str(Path(tmp) / "feedback.jsonl"))
            ts = store.append("great tool", 5, "user@example.com", "k1")
            self.assertTrue(ts)
            content = (Path(tmp) / "feedback.jsonl").read_text(encoding="utf-8")
            self.assertIn("great tool", content)

    def test_eval_service_lists_scenarios(self) -> None:
        service = EvalService(scenarios_path="./data/eval_scenarios.json")
        scenarios = service.list_scenarios()
        self.assertEqual(len(scenarios), 49)


if __name__ == "__main__":
    unittest.main()
