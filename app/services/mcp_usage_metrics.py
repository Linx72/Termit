from __future__ import annotations

from typing import Iterable

MCP_INJECT_EVENTS = frozenset({"mcp_context_injected", "mcp_prompt_injected"})
MCP_TOOL_NAMES = ("mcp_invoke", "mcp_read_resource", "mcp_get_prompt")


def empty_mcp_usage_metrics() -> dict[str, object]:
    return build_mcp_usage_metrics(
        context_inject_total=0,
        prompt_inject_total=0,
        invoke_total=0,
        read_resource_total=0,
        get_prompt_total=0,
        inject_runs=0,
        active_runs=0,
    )


def build_mcp_usage_metrics(
    *,
    context_inject_total: int,
    prompt_inject_total: int,
    invoke_total: int,
    read_resource_total: int,
    get_prompt_total: int,
    inject_runs: int,
    active_runs: int,
) -> dict[str, object]:
    tool_calls = invoke_total + read_resource_total + get_prompt_total
    inject_rate = round(inject_runs / active_runs, 4) if active_runs else 0.0
    return {
        "mcp_context_inject_total": context_inject_total,
        "mcp_prompt_inject_total": prompt_inject_total,
        "mcp_invoke_total": invoke_total,
        "mcp_read_resource_total": read_resource_total,
        "mcp_get_prompt_total": get_prompt_total,
        "mcp_tool_calls_total": tool_calls,
        "mcp_inject_runs": inject_runs,
        "mcp_active_runs": active_runs,
        "mcp_inject_rate": inject_rate,
    }


def aggregate_mcp_usage_events(rows: Iterable[tuple[str, str, str]]) -> dict[str, object]:
    context_inject_total = 0
    prompt_inject_total = 0
    invoke_total = 0
    read_resource_total = 0
    get_prompt_total = 0
    inject_run_ids: set[str] = set()
    active_run_ids: set[str] = set()

    for run_id, event_type, message in rows:
        if event_type == "mcp_context_injected":
            context_inject_total += 1
            inject_run_ids.add(run_id)
            active_run_ids.add(run_id)
            continue
        if event_type == "mcp_prompt_injected":
            prompt_inject_total += 1
            inject_run_ids.add(run_id)
            active_run_ids.add(run_id)
            continue
        if event_type not in {"tool_loop_tool", "tool_loop_tool_error", "tool_loop_step"}:
            continue
        matched = False
        for tool_name in MCP_TOOL_NAMES:
            if f"({tool_name})" in message:
                matched = True
                if tool_name == "mcp_invoke":
                    invoke_total += 1
                elif tool_name == "mcp_read_resource":
                    read_resource_total += 1
                else:
                    get_prompt_total += 1
        if matched:
            active_run_ids.add(run_id)

    return build_mcp_usage_metrics(
        context_inject_total=context_inject_total,
        prompt_inject_total=prompt_inject_total,
        invoke_total=invoke_total,
        read_resource_total=read_resource_total,
        get_prompt_total=get_prompt_total,
        inject_runs=len(inject_run_ids),
        active_runs=len(active_run_ids),
    )
