# Migration Notes 0.4.15

## Scope

MCP usage telemetry in ops metrics, Desktop API, and KPI gates.

Previous stable: `v0.4.14`.

## New endpoints

- `GET /api/desktop/mcp-metrics` — inject/tool counters and adoption rate.

## Ops metrics

`/api/ops/agent-runs/metrics` now includes:

- `mcp_context_inject_total`, `mcp_prompt_inject_total`
- `mcp_invoke_total`, `mcp_read_resource_total`, `mcp_get_prompt_total`
- `mcp_inject_runs`, `mcp_active_runs`, `mcp_inject_rate`

## KPI gates (when enough data)

- `mcp_inject_rate` — active MCP runs ≥ 5
- `mcp_adoption_rate` — tool loop runs ≥ 10

Targets in `data/desktop_north_star.json`.
