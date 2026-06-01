import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.services.finetune_trajectory_export import (
    events_to_messages,
    load_trajectory_sft_rows,
    messages_to_sft_record,
)


class FinetuneTrajectoryExportTests(unittest.TestCase):
    def test_events_to_messages_with_trace_payload(self) -> None:
        events = [
            (
                "tool_loop_trace",
                json.dumps(
                    {
                        "step": 1,
                        "action": "tool",
                        "tool": "read_file",
                        "observation": '{"path":"auth.py","content":"..."}',
                        "assistant": '{"action":"tool","tool":"read_file"}',
                    }
                ),
            ),
        ]
        messages = events_to_messages(
            instruction="Review auth.py",
            events=events,
            final_response="Auth uses constant-time compare.",
        )
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "Review auth.py")
        self.assertEqual(messages[-1]["role"], "assistant")
        self.assertIn("constant-time", messages[-1]["content"])

    def test_messages_to_sft_record_requires_roles(self) -> None:
        self.assertIsNone(messages_to_sft_record([{"role": "user", "content": "x"}]))
        record = messages_to_sft_record(
            [
                {"role": "user", "content": "Fix bug"},
                {"role": "assistant", "content": "Done"},
            ],
            run_id="r1",
        )
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["run_id"], "r1")
        self.assertEqual(len(record["messages"]), 2)

    def test_load_trajectory_sft_rows_from_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "runs.db"
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE agent_runs (
                        run_id TEXT PRIMARY KEY,
                        agent_id TEXT NOT NULL,
                        state TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        input TEXT NOT NULL,
                        response TEXT NOT NULL,
                        error TEXT,
                        failure_class TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE agent_run_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        message TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO agent_runs(
                        run_id, agent_id, state, updated_at, input, response, error, failure_class
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "r1",
                        "a1",
                        "completed",
                        "2026-06-01T00:00:00Z",
                        "Review middleware",
                        "Middleware validates JWT.",
                        None,
                        None,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO agent_run_events(run_id, event_type, message)
                    VALUES (?, ?, ?)
                    """,
                    (
                        "r1",
                        "tool_loop_trace",
                        json.dumps(
                            {
                                "step": 1,
                                "action": "tool",
                                "tool": "read_file",
                                "observation": "file contents",
                                "assistant": '{"action":"tool","tool":"read_file"}',
                            }
                        ),
                    ),
                )
                conn.commit()

            rows, stats = load_trajectory_sft_rows(db_path, limit=10, min_messages=3)
            self.assertEqual(stats.exported, 1)
            self.assertEqual(len(rows), 1)
            self.assertIn("messages", rows[0])


if __name__ == "__main__":
    unittest.main()
