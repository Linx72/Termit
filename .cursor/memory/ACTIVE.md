# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-17

## Сводка

- **v0.4.14** — MCP prompt picker Desktop, `mcp_context_inject` opt-out, eval P5
- Тесты: **545 OK** (skipped=6)

## Файлы сессии

- `app/domain/schemas.py` — `mcp_context_inject`
- `app/services/agent_service.py` — respect opt-out
- `app/services/eval_service.py` — `platform_mcp_prompt`
- `clients/termit-desktop/src/App.tsx`, `settings.ts`, `i18n.ts`
- `clients/termit-client/src/types.ts`
- `data/eval_scenarios.json` — P5

## Открытые задачи

- [ ] Следующий `do all`: MCP inject telemetry в ops dashboard / KPI gate для MCP usage
