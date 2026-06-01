import json
import tempfile
import unittest
from pathlib import Path

from app.services.patch_outcome_store import PatchOutcomeStore
from app.services.tool_loop_tuning_service import build_tool_loop_tuning_report
from app.services.training_signal_store import TrainingSignalStore


class PatchOutcomeStoreTests(unittest.TestCase):
    def test_detects_revert_and_captures_dpo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "app.py"
            target.write_text("version1\n", encoding="utf-8")
            outcomes = PatchOutcomeStore(str(root / "outcomes.jsonl"))
            signals = TrainingSignalStore(str(root / "signals.jsonl"), min_output_chars=4)
            outcomes.record_applied_patch(
                run_id="r1",
                rel_path="app.py",
                root_path=str(root),
                instruction="Fix app entrypoint",
            )
            target.write_text("version2-user-edit\n", encoding="utf-8")
            captured = outcomes.handle_file_changed(
                "app.py",
                root_path=str(root),
                training_signals=signals,
            )
            self.assertTrue(captured)
            dpo = signals.load_dpo_samples(limit=10)
            self.assertEqual(len(dpo), 1)
            self.assertIn("reverted", dpo[0]["rejected"])


class ToolLoopTuningReportTests(unittest.TestCase):
    def test_builds_recommendations_on_parse_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "runs.db"
            import sqlite3

            with sqlite3.connect(db) as conn:
                conn.execute(
                    """
                    CREATE TABLE agent_run_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        message TEXT NOT NULL
                    )
                    """
                )
                for _ in range(4):
                    conn.execute(
                        "INSERT INTO agent_run_events(event_type, message) VALUES (?, ?)",
                        ("tool_loop_parse_error", "invalid json"),
                    )
                conn.commit()
            report = build_tool_loop_tuning_report(
                agent_run_sqlite_path=db,
                training_signals_path=root / "missing.jsonl",
            )
            self.assertGreaterEqual(int(report["event_stats"]["parse_errors"]), 3)
            self.assertTrue(any("parse" in item.lower() for item in report["recommendations"]))


if __name__ == "__main__":
    unittest.main()
