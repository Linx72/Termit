#!/usr/bin/env python3
"""AutoCheckPoint: persist session memory before Cursor compacts context.

Writes compact handoffs to .cursor/memory/ and injects ACTIVE summary on preCompact
so long chats and new agents keep decisions, files touched, and pending work.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(
    os.getenv("CURSOR_PROJECT_DIR") or Path(__file__).resolve().parents[2]
)
MEMORY_ROOT = Path(
    os.getenv("TERMIT_MEMORY_DIR", str(PROJECT_ROOT / ".cursor" / "memory"))
)
CHECKPOINT_DIR = MEMORY_ROOT / "checkpoints"
ACTIVE_FILE = MEMORY_ROOT / "ACTIVE.md"
STATE_DIR = Path(
    os.getenv("TERMIT_HOOK_STATE_DIR")
    or (Path(__file__).resolve().parent / "state")
)
STATE_FILE = STATE_DIR / "session_checkpoint.json"

CHECKPOINT_TOKEN_THRESHOLD = int(
    os.getenv("TERMIT_CHECKPOINT_TOKEN_THRESHOLD", "100000")
)
MAX_TRACKED_FILES = int(os.getenv("TERMIT_CHECKPOINT_MAX_FILES", "80"))
MAX_TRACKED_COMMANDS = int(os.getenv("TERMIT_CHECKPOINT_MAX_COMMANDS", "30"))
MAX_RESPONSE_SNIPPETS = int(os.getenv("TERMIT_CHECKPOINT_MAX_SNIPPETS", "12"))


def _load_env() -> None:
    env_path = Path(__file__).resolve().parent / "session_checkpoint.env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _read_input() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _conv_key(payload: dict) -> str:
    return str(payload.get("conversation_id") or payload.get("session_id") or "global")


def _load_state() -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.is_file():
        return {"conversations": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"conversations": {}}


def _save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _conv_state(state: dict, key: str) -> dict:
    conversations = state.setdefault("conversations", {})
    conv = conversations.setdefault(key, {})
    conv.setdefault("files", [])
    conv.setdefault("commands", [])
    conv.setdefault("snippets", [])
    conv.setdefault("checkpoints", [])
    return conv


def _truncate(text: str, max_len: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def _extract_paths(payload: dict) -> list[str]:
    paths: list[str] = []
    for key in ("path", "file_path", "target_path", "filePath"):
        value = payload.get(key)
        if value:
            paths.append(str(value))
    tool_input = payload.get("tool_input") or payload.get("arguments") or {}
    if isinstance(tool_input, dict):
        for key in ("path", "file_path", "target_path", "filePath"):
            value = tool_input.get(key)
            if value:
                paths.append(str(value))
    return paths


def _track_file(conv: dict, path: str) -> None:
    path = path.strip()
    if not path:
        return
    files: list[str] = conv.setdefault("files", [])
    if path not in files:
        files.append(path)
    if len(files) > MAX_TRACKED_FILES:
        conv["files"] = files[-MAX_TRACKED_FILES:]


def _track_command(conv: dict, command: str) -> None:
    command = _truncate(command, 160)
    if not command:
        return
    commands: list[str] = conv.setdefault("commands", [])
    commands.append(command)
    if len(commands) > MAX_TRACKED_COMMANDS:
        conv["commands"] = commands[-MAX_TRACKED_COMMANDS:]


def _track_snippet(conv: dict, text: str) -> None:
    snippet = _truncate(text, 280)
    if not snippet:
        return
    snippets: list[str] = conv.setdefault("snippets", [])
    if snippets and snippets[-1] == snippet:
        return
    snippets.append(snippet)
    if len(snippets) > MAX_RESPONSE_SNIPPETS:
        conv["snippets"] = snippets[-MAX_RESPONSE_SNIPPETS:]


def _git_snapshot() -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "status", "--short", "-b"],
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )
        if proc.returncode != 0:
            return ""
        body = (proc.stdout or "").strip()
        return body[:2500]
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _format_tokens(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def _build_handoff(
    *,
    conv: dict,
    payload: dict,
    reason: str,
) -> str:
    tokens = int(payload.get("context_tokens") or 0)
    window = int(payload.get("context_window_size") or 0)
    usage = float(payload.get("context_usage_percent") or 0)
    model = str(payload.get("model") or payload.get("subagent_type") or "agent")
    files = conv.get("files", [])
    commands = conv.get("commands", [])
    snippets = conv.get("snippets", [])
    git_status = _git_snapshot()

    lines = [
        f"# AutoCheckPoint — {reason}",
        "",
        f"- **updated:** {_utc_stamp()}",
        f"- **conversation:** `{_conv_key(payload)}`",
        f"- **model:** {model}",
        f"- **context:** {_format_tokens(tokens)}/{_format_tokens(window)} tokens ({usage:.0f}%)",
        f"- **threshold:** {_format_tokens(CHECKPOINT_TOKEN_THRESHOLD)} tokens",
        "",
        "## Что делали (кратко)",
    ]
    if snippets:
        for item in snippets[-8:]:
            lines.append(f"- {item}")
    else:
        lines.append("- (нет зафиксированных ответов агента в этой сессии)")

    lines.extend(["", "## Файлы (трогали в сессии)"])
    if files:
        for path in files[-40:]:
            lines.append(f"- `{path}`")
    else:
        lines.append("- (пока не зафиксировано)")

    lines.extend(["", "## Команды (shell)"])
    if commands:
        for cmd in commands[-15:]:
            lines.append(f"- `{cmd}`")
    else:
        lines.append("- (нет)")

    if git_status:
        lines.extend(["", "## Git", "```", git_status, "```"])

    lines.extend(
        [
            "",
            "## Для следующего агента",
            "1. Прочитай `.cursor/memory/ACTIVE.md` и последний checkpoint в `.cursor/memory/checkpoints/`.",
            "2. Не повторяй уже сделанные шаги; продолжай с открытых задач.",
            "3. Новые важные решения дописывай в ACTIVE или попроси `/checkpoint` вручную.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_checkpoint(
    *,
    conv: dict,
    payload: dict,
    reason: str,
) -> Path:
    MEMORY_ROOT.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    handoff = _build_handoff(conv=conv, payload=payload, reason=reason)
    conv_id = _conv_key(payload)[:24].replace("/", "_")
    filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}_{conv_id}.md"
    path = CHECKPOINT_DIR / filename
    path.write_text(handoff, encoding="utf-8")

    active_body = (
        "# Session memory (AutoCheckPoint)\n\n"
        f"**Последнее обновление:** {_utc_stamp()}\n\n"
        f"**Причина:** {reason}\n\n"
        f"**Последний checkpoint:** [`{filename}`](checkpoints/{filename})\n\n"
        "## Сводка\n"
    )
    snippets = conv.get("snippets", [])
    if snippets:
        active_body += "\n".join(f"- {s}" for s in snippets[-6:])
    else:
        active_body += "- (пусто — начните задачу)\n"

    active_body += "\n\n## Файлы сессии\n"
    files = conv.get("files", [])
    if files:
        active_body += "\n".join(f"- `{p}`" for p in files[-25:])
    else:
        active_body += "- (нет)\n"

    active_body += (
        "\n\n## Открытые задачи\n"
        "- [ ] Заполните вручную или через compact-chat после крупной сессии\n"
    )
    ACTIVE_FILE.write_text(active_body, encoding="utf-8")

    checkpoints: list[str] = conv.setdefault("checkpoints", [])
    checkpoints.append(str(path.relative_to(MEMORY_ROOT)))
    conv["checkpoints"] = checkpoints[-20:]
    conv["last_checkpoint_at"] = _utc_stamp()
    conv["last_checkpoint_reason"] = reason
    return path


def _compact_active_for_injection(max_chars: int = 3500) -> str:
    if not ACTIVE_FILE.is_file():
        return ""
    body = ACTIVE_FILE.read_text(encoding="utf-8").strip()
    if len(body) <= max_chars:
        return body
    return body[: max_chars - 20].rstrip() + "\n…(truncated)"


def _handle_session_start(payload: dict, conv: dict) -> dict:
    context = _compact_active_for_injection()
    if not context:
        return {}
    return {
        "additional_context": (
            "[AutoCheckPoint] Память прошлых сессий (читай перед работой):\n\n"
            f"{context}"
        )
    }


def _handle_post_tool_use(payload: dict, conv: dict) -> dict:
    tool = str(payload.get("tool_name") or "")
    for path in _extract_paths(payload):
        _track_file(conv, path)
    if tool == "Shell":
        command = str(payload.get("command") or "")
        if not command:
            tool_input = payload.get("tool_input") or payload.get("arguments") or {}
            if isinstance(tool_input, dict):
                command = str(tool_input.get("command") or "")
        _track_command(conv, command)
    return {}


def _handle_after_agent_response(payload: dict, conv: dict) -> dict:
    _track_snippet(conv, str(payload.get("text") or ""))
    return {}


def _handle_pre_compact(payload: dict, conv: dict) -> dict:
    tokens = int(payload.get("context_tokens") or 0)
    reason = "preCompact"
    if tokens >= CHECKPOINT_TOKEN_THRESHOLD:
        reason = f"preCompact @ {_format_tokens(tokens)} tokens (≥ threshold)"
    path = _write_checkpoint(conv=conv, payload=payload, reason=reason)
    active = _compact_active_for_injection()
    msg = (
        f"AutoCheckPoint: сохранён снимок `{path.name}` "
        f"({_format_tokens(tokens)} токенов). "
        "Ключевые решения и файлы — в `.cursor/memory/ACTIVE.md`."
    )
    output: dict[str, str] = {"user_message": msg}
    if active:
        output["additional_context"] = (
            "[AutoCheckPoint — сохранено перед compaction]\n\n" + active
        )
    return output


def _handle_stop(payload: dict, conv: dict) -> dict:
    _write_checkpoint(conv=conv, payload=payload, reason="session stop")
    return {}


def main() -> int:
    _load_env()
    payload = _read_input()
    event = str(payload.get("hook_event_name") or "")

    state = _load_state()
    conv = _conv_state(state, _conv_key(payload))

    try:
        if event == "sessionStart":
            output = _handle_session_start(payload, conv)
        elif event == "postToolUse":
            output = _handle_post_tool_use(payload, conv)
        elif event == "afterAgentResponse":
            output = _handle_after_agent_response(payload, conv)
        elif event == "preCompact":
            output = _handle_pre_compact(payload, conv)
        elif event == "stop":
            output = _handle_stop(payload, conv)
        else:
            output = {}
    finally:
        _save_state(state)

    if output:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
