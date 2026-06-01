#!/usr/bin/env python3
"""Project Cursor hook: warn about context window fill and high token burn rate."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

STATE_DIR = Path(
    os.getenv("TERMIT_HOOK_STATE_DIR")
    or (Path(__file__).resolve().parent / "state")
)
STATE_FILE = STATE_DIR / "token_watch.json"

CONTEXT_WARN_PERCENT = int(os.getenv("TERMIT_HOOK_CONTEXT_WARN_PERCENT", "80"))
CONTEXT_CRITICAL_PERCENT = int(os.getenv("TERMIT_HOOK_CONTEXT_CRITICAL_PERCENT", "92"))
RATE_WARN_SCORE_PER_MIN = int(os.getenv("TERMIT_HOOK_RATE_WARN_SCORE_PER_MIN", "120"))
RATE_CRITICAL_SCORE_PER_MIN = int(os.getenv("TERMIT_HOOK_RATE_CRITICAL_SCORE_PER_MIN", "220"))
NOTIFY_COOLDOWN_SEC = int(os.getenv("TERMIT_HOOK_NOTIFY_COOLDOWN_SEC", "120"))

TOOL_WEIGHTS = {
    "Task": 8,
    "Shell": 3,
    "Write": 2,
    "Read": 1,
    "Grep": 1,
    "Delete": 1,
}


def _load_env() -> None:
    env_path = Path(__file__).resolve().parent / "token_watch.env"
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


def _load_state() -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.is_file():
        return {"conversations": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"conversations": {}}


def _save_state(state: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"[token_watch] state save skipped: {exc}", file=sys.stderr)


def _conv_key(payload: dict) -> str:
    return str(payload.get("conversation_id") or payload.get("session_id") or "global")


def _now() -> float:
    return time.time()


def _notify(title: str, message: str) -> None:
    if sys.platform != "darwin":
        print(f"[token_watch] {title}: {message}", file=sys.stderr)
        return
    safe_title = title.replace('"', "'")
    safe_message = message.replace('"', "'")
    script = (
        f'display notification "{safe_message}" '
        f'with title "{safe_title}" sound name "Ping"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        print(f"[token_watch] {title}: {message}", file=sys.stderr)


def _can_notify(conv: dict, key: str, cooldown: int = NOTIFY_COOLDOWN_SEC) -> bool:
    last = float(conv.get(key, 0))
    return _now() - last >= cooldown


def _mark_notify(conv: dict, key: str) -> None:
    conv[key] = _now()


def _append_event(conv: dict, score: float) -> None:
    events = conv.setdefault("events", [])
    events.append({"ts": _now(), "score": score})
    cutoff = _now() - 300
    conv["events"] = [item for item in events if item["ts"] >= cutoff]


def _rate_score_per_min(conv: dict) -> float:
    cutoff = _now() - 60
    events = conv.get("events", [])
    total = sum(item["score"] for item in events if item["ts"] >= cutoff)
    return float(total)


def _format_tokens(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


def _truncate(text: str, max_len: int = 60) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def _register_agent_label(state: dict, agent_id: str, label: str) -> None:
    agent_id = str(agent_id or "").strip()
    label = str(label or "").strip()
    if not agent_id or not label:
        return
    state.setdefault("agents", {})[agent_id] = label


def _resolve_agent_label(payload: dict, state: dict) -> str:
    conv_id = str(payload.get("conversation_id") or payload.get("session_id") or "").strip()
    agents = state.get("agents", {})
    if conv_id and conv_id in agents:
        return agents[conv_id]

    subagent_id = str(payload.get("subagent_id") or "").strip()
    if subagent_id and subagent_id in agents:
        return agents[subagent_id]

    subagent_type = str(payload.get("subagent_type") or "").strip()
    description = str(payload.get("description") or "").strip()
    task = str(payload.get("task") or "").strip()
    model = str(payload.get("model") or "").strip()

    if subagent_type:
        detail = description or _truncate(task)
        if detail:
            return f"{subagent_type} ({detail})"
        return subagent_type

    if model:
        return model

    return "основной чат"


def _remember_agent_label(payload: dict, state: dict) -> None:
    label = _resolve_agent_label(payload, state)
    conv_id = str(payload.get("conversation_id") or payload.get("session_id") or "").strip()
    subagent_id = str(payload.get("subagent_id") or "").strip()
    if conv_id:
        _register_agent_label(state, conv_id, label)
    if subagent_id:
        _register_agent_label(state, subagent_id, label)


def _handle_subagent_start(payload: dict, state: dict) -> dict:
    _remember_agent_label(payload, state)
    return {}


def _handle_pre_compact(payload: dict, conv: dict, state: dict) -> dict:
    usage = float(payload.get("context_usage_percent") or 0)
    tokens = int(payload.get("context_tokens") or 0)
    window = int(payload.get("context_window_size") or 0)
    to_compact = int(payload.get("messages_to_compact") or 0)
    trigger = str(payload.get("trigger") or "auto")
    agent = _resolve_agent_label(payload, state)
    _remember_agent_label(payload, state)

    if usage >= CONTEXT_CRITICAL_PERCENT:
        msg = (
            f"Агент «{agent}»: критическое заполнение контекста — {usage:.0f}% "
            f"({_format_tokens(tokens)}/{_format_tokens(window)} токенов). "
            f"Сейчас будет compaction (~{to_compact} сообщений). "
            "Лучше начать новый чат или убрать лишние @-файлы."
        )
        if _can_notify(conv, "last_context_notify"):
            _notify(f"Termit · контекст · {agent}", msg)
            _mark_notify(conv, "last_context_notify")
        return {"user_message": msg}

    if usage >= CONTEXT_WARN_PERCENT:
        msg = (
            f"Агент «{agent}»: контекст почти заполнен — {usage:.0f}% "
            f"({_format_tokens(tokens)}/{_format_tokens(window)}). "
            f"Trigger={trigger}. Скоро возможна потеря деталей из истории."
        )
        if _can_notify(conv, "last_context_notify"):
            _notify(f"Termit · контекст · {agent}", msg)
            _mark_notify(conv, "last_context_notify")
        return {"user_message": msg}

    return {}


def _handle_post_tool_use(payload: dict, conv: dict, state: dict) -> dict:
    tool = str(payload.get("tool_name") or "tool")
    weight = TOOL_WEIGHTS.get(tool, 1)
    if tool.startswith("MCP:"):
        weight = 2
    _append_event(conv, weight)
    _remember_agent_label(payload, state)
    return _maybe_rate_warning(payload, conv, state)


def _handle_after_agent_response(payload: dict, conv: dict, state: dict) -> dict:
    text = str(payload.get("text") or "")
    est_tokens = max(1, len(text) // 4)
    _append_event(conv, est_tokens / 10)
    _remember_agent_label(payload, state)
    return _maybe_rate_warning(payload, conv, state)


def _handle_stop(payload: dict, conv: dict, state: dict) -> dict:
    return _maybe_rate_warning(payload, conv, state, force=True)


def _maybe_rate_warning(
    payload: dict,
    conv: dict,
    state: dict,
    force: bool = False,
) -> dict:
    score = _rate_score_per_min(conv)
    agent = _resolve_agent_label(payload, state)
    if score >= RATE_CRITICAL_SCORE_PER_MIN and _can_notify(conv, "last_rate_notify"):
        msg = (
            f"Агент «{agent}»: очень высокая трата токенов — ~{score:.0f} score/min "
            f"(порог {RATE_CRITICAL_SCORE_PER_MIN}). "
            "Сократите tool loop, subagent'ы и объём чтений файлов."
        )
        _notify(f"Termit · токены · {agent}", msg)
        _mark_notify(conv, "last_rate_notify")
        return {"additional_context": f"[token_watch] {msg}"}

    if force and score >= RATE_WARN_SCORE_PER_MIN and _can_notify(conv, "last_rate_notify"):
        msg = (
            f"Агент «{agent}»: повышенная трата токенов — ~{score:.0f} score/min "
            f"(порог {RATE_WARN_SCORE_PER_MIN}). "
            "Проверьте, не разросся ли контекст и число tool calls."
        )
        _notify(f"Termit · токены · {agent}", msg)
        _mark_notify(conv, "last_rate_notify")
        return {"additional_context": f"[token_watch] {msg}"}

    return {}


def main() -> int:
    _load_env()
    payload = _read_input()
    event = str(payload.get("hook_event_name") or "")

    state = _load_state()
    conversations = state.setdefault("conversations", {})
    key = _conv_key(payload)
    conv = conversations.setdefault(key, {})

    try:
        if event == "preCompact":
            output = _handle_pre_compact(payload, conv, state)
        elif event == "subagentStart":
            output = _handle_subagent_start(payload, state)
        elif event == "postToolUse":
            output = _handle_post_tool_use(payload, conv, state)
        elif event == "afterAgentResponse":
            output = _handle_after_agent_response(payload, conv, state)
        elif event == "stop":
            output = _handle_stop(payload, conv, state)
        else:
            output = {}
    finally:
        _save_state(state)

    if output:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
