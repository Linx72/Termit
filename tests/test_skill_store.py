import tempfile
import time
import unittest
from pathlib import Path

from app.services.skill_store import SkillStore


class SkillStoreTests(unittest.TestCase):
    def test_progressive_inject_truncates_large_skill(self) -> None:
        root = Path(__file__).resolve().parents[1] / "data" / "skills"
        store = SkillStore(str(root), inject_max_chars=200)
        block = store.build_prompt_block(["media-studio"])
        self.assertIn("truncated", block.lower())
        self.assertIn("read_file", block)

    def test_full_body_inject_skips_truncation(self) -> None:
        root = Path(__file__).resolve().parents[1] / "data" / "skills"
        store = SkillStore(str(root), inject_max_chars=200)
        block = store.build_prompt_block(["media-studio"], full_body=True)
        self.assertNotIn("truncated", block.lower())

    def test_discovery_block_lists_skills(self) -> None:
        root = Path(__file__).resolve().parents[1] / "data" / "skills"
        store = SkillStore(str(root))
        block = store.build_discovery_block()
        self.assertIn("invoke_skill", block)
        self.assertIn("fix-ci", block)

    def test_pinned_full_body_inject(self) -> None:
        root = Path(__file__).resolve().parents[1] / "data" / "skills"
        store = SkillStore(str(root), inject_max_chars=200)
        block = store.build_prompt_block(
            ["media-studio"],
            full_body_skill_ids=frozenset({"media-studio"}),
        )
        self.assertNotIn("truncated", block.lower())

    def test_reload_after_file_touch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "demo-skill"
            skill_dir.mkdir()
            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(
                "---\nname: Demo\ndescription: first\n---\n\n# Demo body\n",
                encoding="utf-8",
            )
            store = SkillStore(tmp)
            first = store.get_skill("demo-skill")
            self.assertIsNotNone(first)
            assert first is not None
            self.assertIn("first", first.description)

            skill_file.write_text(
                "---\nname: Demo\ndescription: second\n---\n\n# Demo body updated\n",
                encoding="utf-8",
            )
            time.sleep(0.05)
            second = store.get_skill("demo-skill")
            self.assertIsNotNone(second)
            assert second is not None
            self.assertIn("second", second.description)


if __name__ == "__main__":
    unittest.main()
