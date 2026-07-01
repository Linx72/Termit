# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-07-01 — browser-интеграция завершена

## Сводка
- **Browser-интеграция:** 12 тулов в agent_service.py + chat_service.py
- **PlaywrightBrowserService:** полноценный класс-обёртка (available, fetch_as_http, snapshot, делегирование)
- **422 тестов passed,** 1 flaky error (test_coder_retries_on_reviewer_issues — предсуществующий)
- **Коммиты:** 4 (исправление site_profiles.json, PlaywrightBrowserService-обёртка, .gitignore, удаление gitlink whisper.cpp)

## Файлы сессии
- `app/services/playwright_browser_service.py` — BrowserSession + PlaywrightBrowserService + эвристики + кэш
- `app/services/agent_tool_schema.py` — 12 browser-схем
- `app/services/agent_service.py` — диспатч browser-тулов
- `app/services/chat_service.py` — диспатч browser-тулов
- `allowed_domains.json`, `site_profiles.json` — конфигурация
- `.gitignore` — auth_state.json + whisper.cpp

## Открытые задачи
- [ ] `OPENAI_COMPAT_API_KEY` в `.env` + GitHub Secrets
- [ ] GPU / `TERMIT_REMOTE_GPU_SSH` → real DPO
- [ ] `TERMIT_BETA_PROD_URL` + real desktop users
