"""Tests for agent long-term memory relevance ranking."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.agent_memory_store import AgentMemoryStore


class AgentMemoryStoreTests(unittest.TestCase):
    def test_get_context_for_task_ranks_by_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AgentMemoryStore(str(Path(tmp) / "mem.db"), max_entries_per_agent=20)
            store.append(
                agent_id="a1",
                outcome="completed",
                summary="Fixed pytest flaky orchestration gate",
                detail="confirm_run timeout in sprint tests",
            )
            store.append(
                agent_id="a1",
                outcome="completed",
                summary="Updated desktop i18n strings",
                detail="Russian translations for health panel",
            )
            lines = store.get_context_for_task(
                "a1",
                task_hint="orchestration gate pytest flaky",
                limit=1,
            )
            self.assertEqual(len(lines), 1)
            self.assertIn("orchestration gate", lines[0].lower())

    def test_get_context_for_task_empty_hint_uses_recency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AgentMemoryStore(str(Path(tmp) / "mem.db"))
            store.append(
                agent_id="a1",
                outcome="completed",
                summary="first task",
                detail="detail one",
            )
            store.append(
                agent_id="a1",
                outcome="completed",
                summary="second task",
                detail="detail two",
            )
            lines = store.get_context_for_task("a1", task_hint="", limit=2)
            self.assertEqual(len(lines), 2)
            self.assertIn("first task", lines[0])
            self.assertIn("second task", lines[1])


if __name__ == "__main__":
    unittest.main()
