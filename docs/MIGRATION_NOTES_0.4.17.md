# Migration Notes 0.4.17

## Scope

MCP metrics in Prometheus and Grafana SLO dashboard.

Previous stable: `v0.4.16`.

## Prometheus

New gauges on `GET /api/metrics/prometheus`:

- `termit_mcp_context_inject_total`, `termit_mcp_prompt_inject_total`
- `termit_mcp_invoke_total`, `termit_mcp_read_resource_total`, `termit_mcp_get_prompt_total`
- `termit_mcp_inject_rate`, `termit_mcp_adoption_rate`

## Grafana

Import or reload `deploy/grafana/dashboards/termit-slo.json` — row **MCP inject & adoption** / **MCP usage counters**.

## Operator checks

1. Scrape `/api/metrics/prometheus`
2. Confirm `termit_mcp_*` series appear after agent runs with MCP tools
