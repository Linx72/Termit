# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-07-01 — браузер v2: 37 тулов (12→37)

## Сводка
- **Browser v2:** 37 тулов в 6 фазах — примитивы, табы, диалоги, визуал, сеть, смарт
- **Файлы:** playwright_browser_service.py (+25 методов), agent_tool_schema.py (+25 схем), agent_service.py (+25 диспатч), chat_service.py (+25 диспатч)
- **TOOL_TIER_BROWSER:** 38 тулов (включая web_automation)
- **Тесты:** 6/6 browser-тестов passed, синтаксис всех 4 файлов OK
- **Коммит:** 4af7546

## Файлы сессии
- `app/services/playwright_browser_service.py` — 46 методов BrowserSession + прокси PlaywrightBrowserService
- `app/services/agent_tool_schema.py` — 37 browser-схем + TOOL_TIER_BROWSER
- `app/services/agent_service.py` — диспатч 37 browser-тулов
- `app/services/chat_service.py` — диспатч 37 browser-тулов
- `allowed_domains.json`, `site_profiles.json` — конфигурация

## Открытые задачи
- [ ] `OPENAI_COMPAT_API_KEY` в `.env` + GitHub Secrets
- [ ] GPU / `TERMIT_REMOTE_GPU_SSH` → real DPO
- [ ] `TERMIT_BETA_PROD_URL` + real desktop users
