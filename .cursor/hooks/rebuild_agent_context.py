#!/usr/bin/env python3
"""Cursor hook: on session end, rebuild project agent prompt and skill archive."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = HOOK_DIR.parent.parent
REBUILD_SCRIPT = PROJECT_ROOT / "scripts" / "rebuild_cursor_agent_context.py"


def _read_input() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def main() -> int:
    payload = _read_input()
    event = payload.get("hook_event_name") or payload.get("event") or "sessionEnd"

    # Fire-and-forget rebuild; never block the UI on failure.
    if not REBUILD_SCRIPT.is_file():
        print(
            json.dumps(
                {
                    "user_message": (
                        "[rebuild_agent_context] скрипт не найден: "
                        f"{REBUILD_SCRIPT}"
                    )
                },
                ensure_ascii=False,
            )
        )
        return 0

    env = os.environ.copy()
    env.setdefault("TERMIT_PROJECT_ROOT", str(PROJECT_ROOT))
    transcripts = os.getenv("TERMIT_AGENT_TRANSCRIPTS_DIR")
    cmd = [sys.executable, str(REBUILD_SCRIPT), "--project-root", str(PROJECT_ROOT)]
    if transcripts:
        cmd.extend(["--transcripts-dir", transcripts])

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=int(os.getenv("TERMIT_REBUILD_TIMEOUT_SEC", "45")),
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        print(
            json.dumps(
                {"user_message": "[rebuild_agent_context] таймаут пересборки архива"},
                ensure_ascii=False,
            )
        )
        return 0

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "unknown error")[:500]
        print(
            json.dumps(
                {
                    "user_message": (
                        f"[rebuild_agent_context] ошибка ({event}): {err}"
                    )
                },
                ensure_ascii=False,
            )
        )
        return 0

    summary = (proc.stdout or "").strip().splitlines()
    tail = summary[-1] if summary else "ok"
    print(
        json.dumps(
            {
                "user_message": (
                    "[rebuild_agent_context] skills и промпт пересобраны из архива. "
                    f"{tail}"
                )
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
