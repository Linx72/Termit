import unittest
from pathlib import Path

from app.domain.schemas import TaskType
from app.services.skill_selector_service import SkillSelectorService
from app.services.skill_store import SkillStore


class SkillSelectorServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        root = Path(__file__).resolve().parents[1] / "data" / "skills"
        cls.store = SkillStore(str(root))
        cls.selector = SkillSelectorService(cls.store, max_skills=3, min_score=3.0, enabled=True)

    def test_selects_fix_ci_for_pipeline_failure(self) -> None:
        result = self.selector.select_skills(
            instruction="GitHub Actions workflow failed on lint step, fix CI",
            task_type=TaskType.coding,
        )
        self.assertIn("fix-ci", result.selected_skill_ids)

    def test_selects_write_tests_for_test_task(self) -> None:
        result = self.selector.select_skills(
            instruction="Add pytest coverage for agent_service edge cases",
            task_type=TaskType.coding,
        )
        self.assertIn("write-tests", result.selected_skill_ids)

    def test_pins_profile_skills_first(self) -> None:
        result = self.selector.select_skills(
            instruction="random task",
            pinned_skill_ids=["security-review"],
            max_skills=2,
        )
        self.assertEqual(result.selected_skill_ids[0], "security-review")
        self.assertEqual(result.selections[0].source, "pinned")

    def test_respects_max_skills(self) -> None:
        result = self.selector.select_skills(
            instruction="fix ci and add tests for security auth flow",
            task_type=TaskType.coding,
            max_skills=2,
        )
        self.assertLessEqual(len(result.selected_skill_ids), 2)

    def test_auto_select_disabled_returns_only_pinned(self) -> None:
        result = self.selector.select_skills(
            instruction="fix ci pipeline",
            pinned_skill_ids=["write-tests"],
            auto_select_enabled=False,
        )
        self.assertEqual(result.selected_skill_ids, ["write-tests"])
        self.assertFalse(result.auto_select_enabled)

    def test_cross_platform_skill_for_mobile_task(self) -> None:
        result = self.selector.select_skills(
            instruction="Build Flutter app for iOS and Android with atomic steps",
            task_type=TaskType.coding,
        )
        self.assertIn("cross-platform-atomic", result.selected_skill_ids)

    def test_no_false_positive_on_common_words(self) -> None:
        result = self.selector.select_skills(
            instruction="Fix GitHub Actions CI and add pytest tests",
            task_type=TaskType.coding,
        )
        self.assertNotIn("agent-guided", result.selected_skill_ids)
        self.assertIn("fix-ci", result.selected_skill_ids)
        self.assertIn("write-tests", result.selected_skill_ids)

    def test_changed_files_boost_fix_ci(self) -> None:
        result = self.selector.select_skills(
            instruction="Investigate failing checks",
            changed_files=[".github/workflows/ci.yml"],
            task_type=TaskType.debug,
        )
        self.assertIn("fix-ci", result.selected_skill_ids)
        fix_ci = next(item for item in result.selections if item.skill_id == "fix-ci")
        self.assertTrue(any(term.startswith("file:") for term in fix_ci.matched_terms))

    def test_selects_termit_platform_for_ops_readiness(self) -> None:
        result = self.selector.select_skills(
            instruction="Improve ops readiness verify pass rate threshold in agent loop",
            task_type=TaskType.coding,
            changed_files=["app/services/ops_service.py"],
        )
        self.assertIn("termit-platform", result.selected_skill_ids)

    def test_relative_cutoff_drops_weak_matches(self) -> None:
        result = self.selector.select_skills(
            instruction="Add pytest unit tests for finetune_service",
            task_type=TaskType.coding,
            max_skills=3,
        )
        self.assertIn("write-tests", result.selected_skill_ids)
        scores = {item.skill_id: item.score for item in result.selections if item.source == "auto"}
        if len(scores) >= 2:
            top = max(scores.values())
            for score in scores.values():
                self.assertGreaterEqual(score, top * 0.55 - 1e-6)


if __name__ == "__main__":
    unittest.main()
