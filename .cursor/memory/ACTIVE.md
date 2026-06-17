# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-17

## Сводка

- **v0.4.15** — MCP usage telemetry (ops metrics, desktop API, KPI gates)
- Тесты: **548 OK** (skipped=6)

## Файлы сессии

- `app/services/mcp_usage_metrics.py` (new)
- `app/services/agent_run_store.py`, `sqlite_agent_run_store.py`
- `app/services/desktop_kpi_gate_service.py`
- `app/api/routes/desktop.py` — `/mcp-metrics`
- `data/desktop_north_star.json`
- `clients/termit-client/src/desktopOps.ts`
- `clients/termit-desktop/src/App.tsx`
- `tests/test_mcp_usage_metrics.py`

## Открытые задачи

- [ ] Следующий `do all`: MCP metrics panel в ops dashboard web UI
