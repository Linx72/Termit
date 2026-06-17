# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-17

## Сводка

- **v0.4.13** — MCP plan prompt inject, Desktop MCP resource picker, eval CP21
- Тесты: **544 OK** (skipped=6); desktop build OK

## Файлы сессии

- `app/services/mcp_context_service.py` — `build_plan_prompt_lines`
- `app/services/agent_service.py` — `mcp_prompt_injected`
- `clients/termit-client/src/client.ts`, `platform.ts` — list resources/prompts
- `clients/termit-desktop/src/App.tsx`, `i18n.ts` — resource picker UI
- `data/eval_scenarios.json` — CP21
- `tests/test_mcp_context_service.py`, `tests/test_eval_service.py`

## Открытые задачи

- [ ] Следующий `do all`: Desktop MCP prompt picker / inject prompt into plan panel
- [ ] Agent run flag `mcp_context_inject=false` для opt-out (optional)
