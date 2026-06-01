import unittest

from app.services.repo_profile_resolver import infer_repo_profile_id


class _Profile:
    def __init__(self, profile_id: str, path_prefix: str) -> None:
        self.profile_id = profile_id
        self.path_prefix = path_prefix


class RepoProfileResolverTests(unittest.TestCase):
    def test_explicit_wins(self) -> None:
        result = infer_repo_profile_id(
            explicit="custom",
            path_prefix="app/services",
            default_profile_id="default",
            list_profiles_fn=lambda: [_Profile("from-path", "app/")],
        )
        self.assertEqual(result, "custom")

    def test_infers_from_path_prefix(self) -> None:
        result = infer_repo_profile_id(
            explicit=None,
            path_prefix="app/services/agent_service.py",
            default_profile_id="default",
            list_profiles_fn=lambda: [_Profile("termit-core", "app/")],
        )
        self.assertEqual(result, "termit-core")

    def test_falls_back_to_default(self) -> None:
        result = infer_repo_profile_id(
            explicit=None,
            path_prefix="",
            default_profile_id="termit-core",
            list_profiles_fn=list,
        )
        self.assertEqual(result, "termit-core")


if __name__ == "__main__":
    unittest.main()
