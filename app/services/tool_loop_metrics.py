from __future__ import annotations

from typing import Iterable


def build_tool_loop_metrics(
    *,
    tool_steps: int,
    tool_errors: int,
    parse_errors: int,
    final_steps: int,
    loop_runs: int,
    completed_loop_runs: int,
) -> dict[str, object]:
    total_tool = tool_steps + tool_errors
    tool_success_rate = round(tool_steps / total_tool, 4) if total_tool else 0.0
    completion_rate = round(completed_loop_runs / loop_runs, 4) if loop_runs else 0.0
    return {
        "tool_loop_runs": loop_runs,
        "tool_loop_tool_steps": tool_steps,
        "tool_loop_tool_errors": tool_errors,
        "tool_loop_parse_errors": parse_errors,
        "tool_loop_final_steps": final_steps,
        "tool_loop_tool_success_rate": tool_success_rate,
        "tool_loop_completion_rate": completion_rate,
    }


def empty_tool_loop_metrics() -> dict[str, object]:
    return build_tool_loop_metrics(
        tool_steps=0,
        tool_errors=0,
        parse_errors=0,
        final_steps=0,
        loop_runs=0,
        completed_loop_runs=0,
    )


def classify_tool_loop_event(event_type: str, message: str) -> str | None:
    if event_type in {
        "tool_loop_tool",
        "tool_loop_tool_error",
        "tool_loop_parse_error",
        "tool_loop_final",
    }:
        return event_type
    if event_type != "tool_loop_step":
        return None
    if ": parse_error" in message:
        return "tool_loop_parse_error"
    if ": final" in message:
        return "tool_loop_final"
    if ": tool (" in message:
        return "tool_loop_tool"
    return None


def aggregate_tool_loop_events(
    rows: Iterable[tuple[str, str, str]],
    completed_run_ids: set[str],
) -> dict[str, object]:
    tool_steps = 0
    tool_errors = 0
    parse_errors = 0
    final_steps = 0
    loop_run_ids: set[str] = set()
    final_run_ids: set[str] = set()

    for run_id, event_type, message in rows:
        classified = classify_tool_loop_event(event_type, message)
        if classified is None:
            continue
        loop_run_ids.add(run_id)
        if classified == "tool_loop_tool":
            tool_steps += 1
        elif classified == "tool_loop_tool_error":
            tool_errors += 1
        elif classified == "tool_loop_parse_error":
            parse_errors += 1
        elif classified == "tool_loop_final":
            final_steps += 1
            final_run_ids.add(run_id)

    completed_loop_runs = len(final_run_ids & completed_run_ids)
    return build_tool_loop_metrics(
        tool_steps=tool_steps,
        tool_errors=tool_errors,
        parse_errors=parse_errors,
        final_steps=final_steps,
        loop_runs=len(loop_run_ids),
        completed_loop_runs=completed_loop_runs,
    )
