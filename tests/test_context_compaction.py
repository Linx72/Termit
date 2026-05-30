import unittest

from app.domain.schemas import ChatMessage
from app.services.context_compaction import ContextCompactor


class ContextCompactionTests(unittest.TestCase):
    def test_no_compaction_within_budget(self) -> None:
        compactor = ContextCompactor(max_messages=10, max_chars=5000)
        messages = [ChatMessage(role="user", content="short")]
        result = compactor.compact(messages)
        self.assertFalse(result.compacted)
        self.assertEqual(len(result.messages), 1)

    def test_drops_old_messages_and_adds_summary(self) -> None:
        compactor = ContextCompactor(max_messages=3, max_chars=5000, summary_max_chars=500)
        messages = [
            ChatMessage(role="user", content=f"old-{index}")
            for index in range(6)
        ]
        result = compactor.compact(messages)
        self.assertTrue(result.compacted)
        self.assertEqual(result.dropped_messages, 3)
        self.assertEqual(result.messages[0].role, "system")
        self.assertIn("[Context compaction]", result.messages[0].content)
        self.assertEqual(result.messages[-1].content, "old-5")

    def test_char_budget_triggers_compaction(self) -> None:
        compactor = ContextCompactor(max_messages=50, max_chars=200, summary_max_chars=120)
        messages = [ChatMessage(role="user", content="x" * 120) for _ in range(4)]
        result = compactor.compact(messages)
        self.assertTrue(result.compacted)
        self.assertGreater(result.dropped_messages, 0)


if __name__ == "__main__":
    unittest.main()
