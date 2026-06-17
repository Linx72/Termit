# Browser MCP (Playwright) — opt-in preset

> **Sprint C parity:** Antigravity-style browser MCP через локальный Playwright bridge.

## Зачем

Агент может вызывать браузер двумя способами:

| Способ | Когда |
|--------|--------|
| Native tools `browser_navigate` / `browser_snapshot` / `browser_click` | Профиль с `allow_online=true`, `TERMIT_BROWSER_BACKEND=playwright` |
| MCP `mcp_invoke` → server `termit-browser` | Явный opt-in, audit в `mcp_audit.jsonl`, RBAC per profile |

MCP preset полезен для online-project агентов и Cursor-style MCP wiring.

## Установка

```bash
pip install playwright
playwright install chromium
export TERMIT_BROWSER_BACKEND=playwright
```

## Включение preset

1. Откройте `data/mcp_servers.json` или Desktop → Platform → MCP servers.
2. Найдите **`termit-browser`** (Termit Browser Playwright).
3. Установите `"enabled": true`.
4. В профиле агента добавьте:
   - `enabled_tools`: `mcp_invoke`
   - `allowed_mcp_servers`: `["termit-browser"]`
   - `allowed_mcp_tools`: `["browser_navigate", "browser_snapshot", "browser_click"]`

## Вызов из agent loop

```json
{
  "tool": "mcp_invoke",
  "arguments": {
    "server_id": "termit-browser",
    "tool_name": "browser_navigate",
    "arguments": { "url": "https://example.com" }
  }
}
```

## Smoke / тесты

```bash
python3 scripts/mcp_termit_browser.py  # stdio — для ручной отладки через MCP client
python3 -m unittest tests.test_mcp_browser_server -v
curl -s http://127.0.0.1:8765/api/platform/mcp/servers | jq '.servers[] | select(.server_id=="termit-browser")'
```

## Безопасность

- `browser_click` требует `confirmed=true` (как native tool).
- Сервер **disabled by default** — включайте только для online-профилей.
- Session API: `GET /api/platform/mcp/servers/{id}/ping|resources|prompts`.
- Все вызовы пишутся в MCP audit log.

## Связанные файлы

- `scripts/mcp_termit_browser.py` — MCP stdio server
- `data/mcp_servers.json` — preset registry
- `app/services/playwright_browser_service.py` — Playwright backend
- `data/skills/online-project/SKILL.md` — workflow skill
