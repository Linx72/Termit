import json
import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import TaskType
from app.services.finetune_adapter_resolver import FinetuneAdapterResolver
from app.services.routing_policy_service import RoutingPolicyService


class RoutingPolicyAdapterTests(unittest.TestCase):
    def test_falls_back_to_registered_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profiles = Path(tmp) / "profiles.json"
            profiles.write_text(json.dumps([]), encoding="utf-8")
            adapters = Path(tmp) / "adapters.json"
            adapters.write_text(
                json.dumps(
                    {
                        "adapters": [
                            {
                                "adapter_id": "a1",
                                "repo_profile_id": "my-repo",
                                "model": "ollama:my-repo-ft",
                                "registered_at": "2026-06-01T00:00:00Z",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            resolver = FinetuneAdapterResolver(str(adapters))
            service = RoutingPolicyService(
                repo_profiles_path=str(profiles),
                adapter_resolver=resolver,
            )
            model = service.resolve_repo_model(
                profile_id="my-repo",
                path_prefix="",
                task_type=TaskType.coding,
            )
            self.assertEqual(model, "ollama:my-repo-ft")


if __name__ == "__main__":
    unittest.main()
