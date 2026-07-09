from __future__ import annotations

from typing import Iterable


def tool_loop_metric_event_filter_sql(column: str = "event_type") -> str:
    """SQL-фильтр событий tool loop KPI (включая patch_verify после apply_patch)."""
    return (
        f"({column} LIKE 'tool_loop_%' "
        f"OR {column} = 'verify_retry_scheduled' "
        f"OR {column} IN ('patch_verify', 'patch_verify_failed'))"
    )


def build_tool_loop_metrics(
    *,
    tool_steps: int,
    tool_errors: int,
    parse_errors: int,
    final_steps: int,
    verify_passes: int,
    verify_failures: int,
    verify_retries: int,
    loop_runs: int,
    completed_loop_runs: int,
) -> dict[str, object]:
    total_tool = tool_steps + tool_errors
    tool_success_rate = round(tool_steps / total_tool, 4) if total_tool else 0.0
    completion_rate = round(completed_loop_runs / loop_runs, 4) if loop_runs else 0.0
    total_verify = verify_passes + verify_failures
    verify_pass_rate = round(verify_passes / total_verify, 4) if total_verify else 0.0
    return {
        "tool_loop_runs": loop_runs,
        "tool_loop_tool_steps": tool_steps,
        "tool_loop_tool_errors": tool_errors,
        "tool_loop_parse_errors": parse_errors,
        "tool_loop_final_steps": final_steps,
        "tool_loop_verify_passes": verify_passes,
        "tool_loop_verify_failures": verify_failures,
        "tool_loop_verify_retries": verify_retries,
        "tool_loop_verify_pass_rate": verify_pass_rate,
        "tool_loop_tool_success_rate": tool_success_rate,
        "tool_loop_completion_rate": completion_rate,
    }


def empty_tool_loop_metrics() -> dict[str, object]:
    return build_tool_loop_metrics(
        tool_steps=0,
        tool_errors=0,
        parse_errors=0,
        final_steps=0,
        verify_passes=0,
        verify_failures=0,
        verify_retries=0,
        loop_runs=0,
        completed_loop_runs=0,
    )


def classify_tool_loop_event(event_type: str, message: str) -> str | None:
    if event_type in {
        "tool_loop_tool",
        "tool_loop_tool_error",
        "tool_loop_parse_error",
        "tool_loop_final",
        "tool_loop_verify_pass",
        "tool_loop_verify_failed",
        "patch_verify",
        "patch_verify_failed",
        "verify_retry_scheduled",
    }:
        if event_type == "patch_verify":
            return "tool_loop_verify_pass"
        if event_type == "patch_verify_failed":
            return "tool_loop_verify_failed"
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
    verify_passes = 0
    verify_failures = 0
    verify_retries = 0
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
        elif classified == "tool_loop_verify_pass":
            verify_passes += 1
        elif classified == "tool_loop_verify_failed":
            verify_failures += 1
        elif classified == "verify_retry_scheduled":
            verify_retries += 1

    completed_loop_runs = len(final_run_ids & completed_run_ids)
    return build_tool_loop_metrics(
        tool_steps=tool_steps,
        tool_errors=tool_errors,
        parse_errors=parse_errors,
        final_steps=final_steps,
        verify_passes=verify_passes,
        verify_failures=verify_failures,
        verify_retries=verify_retries,
        loop_runs=len(loop_run_ids),
        completed_loop_runs=completed_loop_runs,
    )
