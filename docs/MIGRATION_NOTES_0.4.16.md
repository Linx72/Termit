# Migration Notes 0.4.16

## Scope

MCP usage cards on the web operator dashboard.

Previous stable: `v0.4.15`.

## UI changes

- Operator dashboard (`/` → Панель) shows three MCP cards fed by `/api/ops/agent-runs/metrics`.
- Warning state when inject/adoption fall below north-star targets (same as KPI gates).

## Operator checks

1. Open web UI → refresh dashboard
2. Verify MCP cards populate after agent runs with MCP tools
