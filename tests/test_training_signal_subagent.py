import tempfile
import unittest
from pathlib import Path

from app.services.training_signal_store import TrainingSignalStore


class TrainingSignalSubagentTests(unittest.TestCase):
    def test_capture_subagent_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TrainingSignalStore(str(Path(tmp) / "signals.jsonl"))
            captured = store.try_capture_subagent_run(
                parent_run_id="parent_1",
                child_run_id="child_1",
                task="Explore auth module",
                success=True,
                summary='{"state":"completed"}',
            )
            self.assertTrue(captured)
            samples = store.load_samples(limit=5)
            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0].get("category"), "subagent")


if __name__ == "__main__":
    unittest.main()
