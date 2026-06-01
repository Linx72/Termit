# Agent context per project

Каждый репозиторий получает свою папку после пересборки из архива Cursor-чатов:

```
.cursor/agent/projects/<slug>/new-agent-prompt.md
```

- **Termit:** `slug` = `termit` → `.cursor/agent/projects/termit/new-agent-prompt.md`
- Дубликат для @-mention: `.cursor/NEW_AGENT_PROMPT.md`

Пересборка: `python3 scripts/rebuild_cursor_agent_context.py` или автоматически на `sessionEnd` (см. `.cursor/hooks.json`).
