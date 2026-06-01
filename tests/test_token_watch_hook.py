from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HOOK = Path(__file__).resolve().parents[1] / ".cursor" / "hooks" / "token_watch.py"
DISPATCHER = Path.home() / ".cursor" / "hooks" / "run_token_watch.py"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TokenWatchHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self._state_dir = tempfile.TemporaryDirectory()
        self.env = os.environ.copy()
        self.env["TERMIT_HOOK_STATE_DIR"] = self._state_dir.name

    def tearDown(self) -> None:
        self._state_dir.cleanup()

    def _run_hook(self, payload: dict) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
            env=self.env,
        )

    def test_pre_compact_warns_at_threshold(self) -> None:
        payload = {
            "hook_event_name": "preCompact",
            "conversation_id": "unit-test",
            "model": "composer-2.5-fast",
            "context_usage_percent": 85,
            "context_tokens": 108800,
            "context_window_size": 128000,
            "messages_to_compact": 12,
            "trigger": "auto",
        }
        result = self._run_hook(payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        output = json.loads(result.stdout)
        self.assertIn("user_message", output)
        self.assertIn("85%", output["user_message"])
        self.assertIn("composer-2.5-fast", output["user_message"])

    def test_pre_compact_uses_subagent_label(self) -> None:
        start_payload = {
            "hook_event_name": "subagentStart",
            "conversation_id": "subagent-conv",
            "subagent_id": "subagent-conv",
            "subagent_type": "explore",
            "description": "Search codebase",
        }
        start_result = self._run_hook(start_payload)
        self.assertEqual(start_result.returncode, 0, msg=start_result.stderr)

        compact_payload = {
            "hook_event_name": "preCompact",
            "conversation_id": "subagent-conv",
            "context_usage_percent": 92,
            "context_tokens": 118000,
            "context_window_size": 128000,
            "messages_to_compact": 20,
            "trigger": "auto",
        }
        result = self._run_hook(compact_payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        output = json.loads(result.stdout)
        self.assertIn("explore (Search codebase)", output["user_message"])
        self.assertIn("92%", output["user_message"])

    def test_post_tool_use_is_silent_below_threshold(self) -> None:
        payload = {
            "hook_event_name": "postToolUse",
            "conversation_id": "unit-test-quiet",
            "tool_name": "Read",
        }
        result = self._run_hook(payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    @unittest.skipUnless(DISPATCHER.is_file(), "global dispatcher not installed")
    def test_dispatcher_uses_project_hook(self) -> None:
        payload = {
            "hook_event_name": "preCompact",
            "conversation_id": "dispatcher-test",
            "context_usage_percent": 85,
            "context_tokens": 108800,
            "context_window_size": 128000,
            "messages_to_compact": 12,
            "trigger": "auto",
        }
        env = self.env.copy()
        env["CURSOR_PROJECT_DIR"] = str(PROJECT_ROOT)
        result = subprocess.run(
            [sys.executable, str(DISPATCHER)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        output = json.loads(result.stdout)
        self.assertIn("user_message", output)
        self.assertIn("85%", output["user_message"])


if __name__ == "__main__":
    unittest.main()
