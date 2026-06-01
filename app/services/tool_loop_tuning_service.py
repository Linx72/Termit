from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Optional


def _scan_training_signals(path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not path.exists():
        return counts
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        origin = str(item.get("origin", ""))
        if origin:
            counts[origin] += 1
    return counts


def _scan_agent_run_events(db_path: Path, *, limit: int = 5000) -> dict[str, object]:
    stats: dict[str, object] = {
        "parse_errors": 0,
        "tool_errors": 0,
        "verify_failures": 0,
        "tool_calls": Counter(),
        "event_types": Counter(),
    }
    if not db_path.exists():
        return stats
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                """
                SELECT event_type, message
                FROM agent_run_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    except sqlite3.Error:
        return stats

    tool_calls: Counter[str] = Counter()
    event_types: Counter[str] = Counter()
    parse_errors = 0
    tool_errors = 0
    verify_failures = 0

    for event_type, message in rows:
        et = str(event_type or "")
        event_types[et] += 1
        if et == "tool_loop_parse_error":
            parse_errors += 1
        if et == "tool_loop_tool_error":
            tool_errors += 1
        if et in {"patch_verify_failed", "tool_loop_step"} and "verify failed" in str(message).lower():
            verify_failures += 1
        if et == "tool_loop_trace":
            try:
                payload = json.loads(str(message or ""))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                tool = str(payload.get("tool", "") or "unknown")
                tool_calls[tool] += 1

    stats["parse_errors"] = parse_errors
    stats["tool_errors"] = tool_errors
    stats["verify_failures"] = verify_failures
    stats["tool_calls"] = dict(tool_calls.most_common(12))
    stats["event_types"] = dict(event_types.most_common(12))
    return stats


def build_tool_loop_tuning_report(
    *,
    agent_run_sqlite_path: str | Path,
    training_signals_path: str | Path,
    event_limit: int = 5000,
) -> dict[str, object]:
    signal_counts = _scan_training_signals(Path(training_signals_path))
    event_stats = _scan_agent_run_events(Path(agent_run_sqlite_path), limit=event_limit)

    parse_errors = int(event_stats.get("parse_errors", 0))
    tool_errors = int(event_stats.get("tool_errors", 0))
    verify_failures = int(event_stats.get("verify_failures", 0))
    reverts = int(signal_counts.get("patch_revert", 0))
    negatives = int(signal_counts.get("tool_step_negative", 0))

    recommendations: list[str] = []
    if parse_errors >= 3:
        recommendations.append(
            "Elevated JSON parse errors: tighten LOOP_SYSTEM_APPENDIX with one concrete tool example "
            "and enable native function calling for compat providers."
        )
    if tool_errors >= 5:
        recommendations.append(
            "Frequent tool errors: review RBAC allowlists and add path/heuristic hints in agent system prompt."
        )
    if verify_failures >= 3:
        recommendations.append(
            "Verify failures after patch: ensure verify_command_resolver matches repo test runner "
            "and include failing stdout in the retry user message."
        )
    if reverts >= 2:
        recommendations.append(
            "User reverts detected: export DPO negatives and down-rank similar patch trajectories in curator."
        )
    tool_calls = event_stats.get("tool_calls")
    if isinstance(tool_calls, dict) and tool_calls.get("apply_patch", 0) > 20:
        recommendations.append(
            "High apply_patch volume: add dry_run confirmation step for risky paths in tool policy."
        )
    if not recommendations:
        recommendations.append("No critical tool-loop tuning signals in the recent window.")

    return {
        "signal_origins": dict(signal_counts),
        "event_stats": {
            "parse_errors": parse_errors,
            "tool_errors": tool_errors,
            "verify_failures": verify_failures,
            "tool_calls": event_stats.get("tool_calls", {}),
            "event_types": event_stats.get("event_types", {}),
        },
        "dpo_negative_count": negatives + reverts,
        "recommendations": recommendations,
    }
