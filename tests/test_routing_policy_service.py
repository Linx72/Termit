import unittest
from dataclasses import replace
from unittest.mock import patch

from app.domain.schemas import TaskType
from app.services.model_router import ModelRouter
from app.services.routing_policy_service import RepoModelProfile, RoutingPolicyService
from tests.test_model_router import build_settings


class RoutingPolicyServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = RoutingPolicyService(
            repo_profiles_path="./data/repo_model_profiles.json",
            benchmarks_path="./data/routing_benchmarks.json",
        )

    def test_list_repo_profiles(self) -> None:
        profiles = self.service.list_repo_profiles()
        self.assertGreaterEqual(len(profiles), 3)

    def test_resolve_profile_by_id(self) -> None:
        model = self.service.resolve_repo_model(
            profile_id="termit-core",
            path_prefix="",
            task_type=TaskType.coding,
        )
        self.assertEqual(model, "ollama:termit-core-ft")

    def test_benchmark_ranking_prefers_high_score(self) -> None:
        ranked = self.service.rank_models_for_task(
            [
                "ollama:deepseek-coder",
                "openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct",
            ],
            TaskType.coding,
        )
        self.assertEqual(ranked[0], "openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct")

    def test_model_router_applies_repo_profile(self) -> None:
        router = ModelRouter(build_settings(), routing_policy=self.service)
        models = router.candidate_models(
            TaskType.coding,
            message="implement parser",
            repo_profile="termit-core",
            path_prefix="app/services",
            routing_policy="default",
        )
        self.assertEqual(models[0], "ollama:termit-core-ft")

    def test_model_router_benchmark_reorders_candidates(self) -> None:
        settings = replace(
            build_settings(),
            code_model="ollama:deepseek-coder",
            code_fallback_model="openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct",
        )
        router = ModelRouter(settings, routing_policy=self.service)
        models = router.candidate_models(
            TaskType.coding,
            message="implement parser",
            routing_policy="benchmark",
        )
        self.assertEqual(models[0], "openai_compat:Qwen/Qwen2.5-Coder-32B-Instruct")

    def test_shadow_model_selected_by_traffic_percent(self) -> None:
        profile = RepoModelProfile(
            profile_id="shadow-test",
            title="Shadow test",
            path_prefix="",
            task_type="coding",
            preferred_model="ollama:termit-core-ft",
            shadow_model="ollama:shadow-ft",
            shadow_traffic_percent=10.0,
        )
        with patch.object(self.service, "get_repo_profile", return_value=profile):
            with patch("app.services.routing_policy_service.random.random", return_value=0.05):
                self.assertEqual(
                    self.service.resolve_repo_model(
                        profile_id="shadow-test",
                        path_prefix="",
                        task_type=TaskType.coding,
                    ),
                    "ollama:shadow-ft",
                )
            with patch("app.services.routing_policy_service.random.random", return_value=0.50):
                self.assertEqual(
                    self.service.resolve_repo_model(
                        profile_id="shadow-test",
                        path_prefix="",
                        task_type=TaskType.coding,
                    ),
                    "ollama:termit-core-ft",
                )


if __name__ == "__main__":
    unittest.main()
