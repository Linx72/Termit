from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "rebuild_cursor_agent_context.py"
HOOK = PROJECT_ROOT / ".cursor" / "hooks" / "rebuild_agent_context.py"


class RebuildCursorAgentContextTests(unittest.TestCase):
    def test_collect_digest_from_fixture_transcripts(self) -> None:
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        try:
            from rebuild_cursor_agent_context import (  # type: ignore[import-untyped]
                collect_transcript_digest,
            )
        finally:
            sys.path.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcripts = root / "agent-transcripts"
            session_id = "abc-123"
            session_dir = transcripts / session_id
            session_dir.mkdir(parents=True)
            row = {
                "role": "user",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": "<user_query>\nСделай do all для platform parity\n</user_query>",
                        }
                    ]
                },
            }
            tool_row = {
                "role": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"path": str(root / "app/services/agent_service.py")},
                        }
                    ]
                },
            }
            main = session_dir / f"{session_id}.jsonl"
            main.write_text(
                json.dumps(row, ensure_ascii=False) + "\n" + json.dumps(tool_row) + "\n",
                encoding="utf-8",
            )

            digest = collect_transcript_digest(transcripts, root)
            self.assertEqual(digest.parent_sessions, 1)
            self.assertEqual(digest.user_turns, 1)
            self.assertGreater(digest.theme_counts.get("do_all", 0), 0)
            self.assertIn("app/services/agent_service.py", digest.path_counts)

    def test_rebuild_script_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cursor" / "skills" / "termit-agent" / "archive").mkdir(
                parents=True
            )
            (root / ".cursor" / "skills" / "termit-agent" / "archive" / "reference-sessions-baseline.md").write_text(
                "## One-liner для новых чатов\n\n> Test one-liner.\n",
                encoding="utf-8",
            )
            transcripts = root / "agent-transcripts"
            session_id = "sess-1"
            session_dir = transcripts / session_id
            session_dir.mkdir(parents=True)
            (session_dir / f"{session_id}.jsonl").write_text(
                json.dumps(
                    {
                        "role": "user",
                        "message": {"content": [{"type": "text", "text": "hello"}]},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--project-root",
                    str(root),
                    "--transcripts-dir",
                    str(transcripts),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            generated = (
                root
                / ".cursor"
                / "skills"
                / "termit-agent"
                / "archive"
                / "generated-from-transcripts.md"
            )
            self.assertTrue(generated.is_file())
            prompt = root / ".cursor" / "NEW_AGENT_PROMPT.md"
            self.assertTrue(prompt.is_file())
            self.assertIn("Test one-liner", prompt.read_text(encoding="utf-8"))

    def test_session_end_hook_runs(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"hook_event_name": "sessionEnd", "session_id": "t"}),
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            check=False,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        out = json.loads(proc.stdout)
        self.assertIn("user_message", out)
        self.assertIn("rebuild_agent_context", out["user_message"])


if __name__ == "__main__":
    unittest.main()
