import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import AgentRunEvent, AgentRunRecordResponse, AgentRunState
from app.services.sqlite_agent_run_store import SQLiteAgentRunStore


class SQLiteAgentRunStoreTests(unittest.TestCase):
    def test_put_get_and_list_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteAgentRunStore(str(Path(tmp) / "agent_runs.db"))
            run = AgentRunRecordResponse(
                run_id="arun_1",
                agent_id="agt_1",
                agent_name="Test Agent",
                state=AgentRunState.completed,
                created_at="2026-01-01T00:00:00+00:00",
                updated_at="2026-01-01T00:01:00+00:00",
                input="hello",
                session_id="sess_1",
                provider="ollama",
                model="ollama:qwen",
                attempts=2,
                max_attempts=3,
                failure_class=None,
                attempted_models=["ollama:qwen", "openai_compat:qwen"],
                response="ok",
                error=None,
            )
            store.put_run(run)
            store.append_event(
                "arun_1",
                AgentRunEvent(
                    event_type="run_completed",
                    state=AgentRunState.completed,
                    message="done",
                    timestamp="2026-01-01T00:01:00+00:00",
                    attempt=2,
                ),
            )
            loaded = store.get_run("arun_1")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.agent_id, "agt_1")
            self.assertEqual(loaded.attempted_models, ["ollama:qwen", "openai_compat:qwen"])
            self.assertEqual(loaded.attempts, 2)
            self.assertEqual(loaded.max_attempts, 3)

            listed = store.list_runs(limit=10)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0].run_id, "arun_1")

            listed_agent = store.list_runs_by_agent("agt_1", limit=10)
            self.assertEqual(len(listed_agent), 1)
            self.assertEqual(listed_agent[0].run_id, "arun_1")
            events = store.get_events("arun_1")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].event_type, "run_completed")

            counts = store.count_runs_by_state()
            self.assertEqual(counts.get("completed"), 1)
            self.assertEqual(store.count_runs(), 1)

            deleted = store.trim_events("arun_1", max_events=1)
            self.assertEqual(deleted, 0)

            preview_runs, preview_events = store.cleanup_old_runs(
                cutoff_iso="2030-01-01T00:00:00+00:00",
                terminal_states={AgentRunState.completed},
                dry_run=True,
            )
            self.assertEqual(preview_runs, 1)
            self.assertEqual(preview_events, 1)
            self.assertEqual(store.count_runs(), 1)

            deleted_runs, deleted_events = store.cleanup_old_runs(
                cutoff_iso="2030-01-01T00:00:00+00:00",
                terminal_states={AgentRunState.completed},
                dry_run=False,
            )
            self.assertEqual(deleted_runs, 1)
            self.assertEqual(deleted_events, 1)
            self.assertEqual(store.count_runs(), 0)

    def test_tool_loop_metrics_recent_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteAgentRunStore(str(Path(tmp) / "agent_runs.db"))
            run_old = AgentRunRecordResponse(
                run_id="arun_old",
                agent_id="agt_1",
                agent_name="Agent",
                state=AgentRunState.completed,
                created_at="2020-01-01T00:00:00+00:00",
                updated_at="2020-01-01T00:01:00+00:00",
                input="old",
                session_id="sess_1",
                provider="ollama",
                model="ollama:qwen",
                attempts=1,
                max_attempts=3,
                response="ok",
            )
            run_new = AgentRunRecordResponse(
                run_id="arun_new",
                agent_id="agt_1",
                agent_name="Agent",
                state=AgentRunState.completed,
                created_at="2026-06-19T00:00:00+00:00",
                updated_at="2026-06-19T00:01:00+00:00",
                input="new",
                session_id="sess_2",
                provider="ollama",
                model="ollama:qwen",
                attempts=1,
                max_attempts=3,
                response="ok",
            )
            store.put_run(run_old)
            store.put_run(run_new)
            store.append_event(
                "arun_old",
                AgentRunEvent(
                    event_type="tool_loop_tool_error",
                    state=AgentRunState.running,
                    message="old error",
                    timestamp="2020-01-01T00:00:30+00:00",
                    attempt=1,
                ),
            )
            store.append_event(
                "arun_new",
                AgentRunEvent(
                    event_type="tool_loop_tool",
                    state=AgentRunState.running,
                    message="ok",
                    timestamp="2026-06-19T00:00:30+00:00",
                    attempt=1,
                ),
            )
            store.append_event(
                "arun_new",
                AgentRunEvent(
                    event_type="tool_loop_final",
                    state=AgentRunState.completed,
                    message="done",
                    timestamp="2026-06-19T00:01:00+00:00",
                    attempt=1,
                ),
            )
            all_metrics = store.tool_loop_event_metrics()
            recent = store.tool_loop_event_metrics(recent_days=7)
            self.assertEqual(all_metrics["tool_loop_runs"], 2)
            self.assertEqual(recent["tool_loop_runs"], 1)
            self.assertEqual(recent["tool_loop_completion_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
