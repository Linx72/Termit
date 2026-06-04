from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HOOK = Path(__file__).resolve().parents[1] / ".cursor" / "hooks" / "session_checkpoint.py"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class SessionCheckpointHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.memory_dir = Path(self._tmp.name) / "memory"
        self.state_dir = Path(self._tmp.name) / "state"
        self.env = os.environ.copy()
        self.env["TERMIT_MEMORY_DIR"] = str(self.memory_dir)
        self.env["TERMIT_HOOK_STATE_DIR"] = str(self.state_dir)
        self.env["CURSOR_PROJECT_DIR"] = str(PROJECT_ROOT)
        self.env["TERMIT_CHECKPOINT_TOKEN_THRESHOLD"] = "100000"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, payload: dict) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
            env=self.env,
        )

    def test_pre_compact_writes_checkpoint_and_active(self) -> None:
        track = {
            "hook_event_name": "postToolUse",
            "conversation_id": "cp-test",
            "tool_name": "Write",
            "path": "app/foo.py",
        }
        self.assertEqual(self._run(track).returncode, 0)

        payload = {
            "hook_event_name": "preCompact",
            "conversation_id": "cp-test",
            "context_tokens": 108_000,
            "context_window_size": 128_000,
            "context_usage_percent": 84,
            "model": "composer-2.5-fast",
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        output = json.loads(result.stdout)
        self.assertIn("user_message", output)
        self.assertIn("AutoCheckPoint", output["user_message"])
        self.assertIn("additional_context", output)

        active = self.memory_dir / "ACTIVE.md"
        self.assertTrue(active.is_file())
        self.assertIn("app/foo.py", active.read_text(encoding="utf-8"))

        checkpoints = list((self.memory_dir / "checkpoints").glob("*.md"))
        self.assertEqual(len(checkpoints), 1)
        body = checkpoints[0].read_text(encoding="utf-8")
        self.assertIn("app/foo.py", body)
        self.assertIn("100.0K", body)

    def test_session_start_injects_active(self) -> None:
        active = self.memory_dir / "ACTIVE.md"
        self.memory_dir.mkdir(parents=True)
        active.write_text("# test\n\n- remembered decision\n", encoding="utf-8")

        result = self._run(
            {
                "hook_event_name": "sessionStart",
                "conversation_id": "start-test",
            }
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        output = json.loads(result.stdout)
        self.assertIn("remembered decision", output["additional_context"])


if __name__ == "__main__":
    unittest.main()
