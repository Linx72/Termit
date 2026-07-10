# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-07-09 — KPI 10/12 green, agent_run_success ≥75%, MCP adoption blocked

## Сводка
- **Verify fix (commit e680ae1):** `TERMIT_AGENT_VERIFY_TIMEOUT_SECONDS=120`, smoke verify cmd, `patch_verify` в KPI/SQLite
- **Корень verify 0%:** `execute_command` timeout 30s при unittest ~45s → `Command timed out`
- **Прогон:** 49+ smoke agent runs completed; verify_pass_rate **~83%**
- **KPI gates:** **10/12 green** — tool_loop completion/success 100%, agent_run_success **75.25%**
- **Red gates:** `d30_retention` (dev seed), `mcp_adoption_rate` (0% — модель не вызывает mcp_invoke)
- **Данные DPO:** 7013 signals, 216 DPO pairs — готовы к RunPod
- **MCP:** `termit-browser` enabled; agent `agt_0f2516970f6b` (MCP Smoke) создан
- **`.env`:** `TERMIT_AGENT_RUN_TIMEOUT_SECONDS=600` добавлен локально

## Файлы (verify fix)
- `app/core/config.py`, `app/services/agent_service.py`, `app/services/tool_loop_metrics.py`
- `app/services/sqlite_agent_run_store.py`, `app/state.py`, `.env.example`
- `tests/test_config_parsing.py`, `tests/test_tool_loop_metrics.py`
- `.env`: smoke verify + timeout (не в git)

## Открытые задачи
- [ ] `TERMIT_REMOTE_GPU_SSH` → `./scripts/learning_loop_0423.sh` (real DPO)
- [ ] `TERMIT_BETA_PROD_URL` + 5+ real desktop users, D30 ≥35%
- [ ] MCP adoption: агент без explicit allowlist + модель должна реально вызвать `mcp_invoke` (сейчас final на step 1)
- [ ] Policy preset intersection: `agt_8a6ebdd0b3ab` не получает mcp_invoke из autopilot (by design)
- [ ] DLQ legacy: cleanup dry-run удалит 3 run >7d; bulk replay не нужен
- [x] Agent verify KPI ≥70% ✅
- [x] agent_run_success_rate ≥75% ✅
- [x] Commit e680ae1 на main (local, ahead origin by 1)
