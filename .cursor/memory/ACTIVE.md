# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-17

## Сводка

- **v0.4.12** — MCP resource inject в agent context, tools `mcp_read_resource`/`mcp_get_prompt`, eval P4 `platform_mcp_read`
- Тесты: **543 OK** (skipped=6)

## Файлы сессии

- `app/services/mcp_context_service.py` (new)
- `app/services/agent_service.py` — inject + tool handlers
- `app/services/agent_tool_schema.py` — new tools + companion auto-enable
- `app/services/eval_service.py` — `platform_mcp_read` runner
- `data/eval_scenarios.json` — P4
- `tests/test_mcp_context_service.py` (new)
- `tests/test_eval_service.py`, `tests/test_rbac_and_platform.py` — 75 scenarios
- `VERSION`, `CHANGELOG.md`, `docs/MIGRATION_NOTES_0.4.12.md`, `PROJECT_TASK_PROMPT_RU.md`

## Открытые задачи

- [ ] Следующий `do all`: MCP prompt inject в plan mode / Desktop MCP resource picker
- [ ] Eval MS12 cursor parity MCP read scenario (optional CP12)
