import json
import tempfile
import unittest
from pathlib import Path

from app.services.training_signal_store import TrainingSignalStore


class TrainingSignalStoreTests(unittest.TestCase):
    def test_capture_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TrainingSignalStore(
                str(Path(tmp) / "signals.jsonl"),
                min_output_chars=8,
            )
            first = store.try_capture_agent_run(
                run_id="r1",
                instruction="Review auth middleware",
                response="Auth middleware uses constant-time compare for tokens.",
            )
            second = store.try_capture_agent_run(
                run_id="r1",
                instruction="Review auth middleware",
                response="Duplicate should be ignored.",
            )
            self.assertTrue(first)
            self.assertFalse(second)
            samples = store.load_samples(limit=10)
            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0]["run_id"], "r1")

    def test_short_output_is_not_captured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TrainingSignalStore(
                str(Path(tmp) / "signals.jsonl"),
                min_output_chars=32,
            )
            captured = store.try_capture_task(
                task_id="t1",
                instruction="Add endpoint",
                report="done",
            )
            self.assertFalse(captured)
            self.assertEqual(store.load_samples(), [])

    def test_append_only_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "signals.jsonl"
            store = TrainingSignalStore(str(path), min_output_chars=8)
            store.try_capture_task(
                task_id="t1",
                instruction="Implement health endpoint",
                report="Implemented GET /health with dependency checks.",
            )
            before = path.read_text(encoding="utf-8")
            store.try_capture_task(
                task_id="t1",
                instruction="Implement health endpoint",
                report="Should not overwrite previous row.",
            )
            after = path.read_text(encoding="utf-8")
            self.assertEqual(before, after)
            rows = [json.loads(line) for line in after.splitlines()]
            self.assertEqual(len(rows), 1)

    def test_capture_negative_tool_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TrainingSignalStore(
                str(Path(tmp) / "signals.jsonl"),
                min_output_chars=8,
            )
            observation = json.dumps(
                {
                    "applied": True,
                    "verify": {"executed": True, "exit_code": 1},
                }
            )
            captured = store.try_capture_negative_tool_step(
                run_id="r9",
                step=3,
                action="tool",
                tool="apply_patch",
                observation=observation,
                instruction="Fix auth bug",
                reason="verify_failed",
            )
            self.assertTrue(captured)
            dpo = store.load_dpo_samples(limit=10)
            self.assertEqual(len(dpo), 1)
            self.assertEqual(dpo[0]["rejected"], observation)

    def test_capture_tool_step_on_verified_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TrainingSignalStore(
                str(Path(tmp) / "signals.jsonl"),
                min_output_chars=8,
            )
            observation = json.dumps(
                {
                    "applied": True,
                    "verify": {"executed": True, "exit_code": 0},
                }
            )
            captured = store.try_capture_tool_step(
                run_id="r9",
                step=2,
                action="tool",
                tool="apply_patch",
                observation=observation,
                instruction="Fix auth bug",
                verified=True,
            )
            self.assertTrue(captured)
            self.assertFalse(
                store.try_capture_tool_step(
                    run_id="r9",
                    step=2,
                    action="tool",
                    tool="apply_patch",
                    observation=observation,
                    instruction="Fix auth bug",
                    verified=True,
                )
            )
            samples = store.load_samples(limit=10)
            self.assertEqual(len(samples), 1)
            self.assertEqual(samples[0]["category"], "tool_loop")


if __name__ == "__main__":
    unittest.main()
