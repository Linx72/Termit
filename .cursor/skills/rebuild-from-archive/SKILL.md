---
name: rebuild-from-archive
description: >-
  Rebuilds this repo's Cursor agent skill archive and new-agent prompt from
  agent-transcripts under ~/.cursor/projects. Use when the user archives a chat,
  asks to refresh skills from session archive, or wants a per-project prompt for
  new agents.
---

# Пересборка skill и промпта из архива

## Когда применять

- Пользователь архивирует чат / просит «пересобери skill из архива»
- Нужен актуальный промпт для **нового** агента в этом репозитории
- После крупного спринта — обновить сводку сессий

## Автоматика

При `sessionEnd` хук `.cursor/hooks/rebuild_agent_context.py` вызывает:

```bash
python3 scripts/rebuild_cursor_agent_context.py
```

## Ручной запуск

```bash
cd /path/to/project
python3 scripts/rebuild_cursor_agent_context.py

# Явный каталог транскриптов:
TERMIT_AGENT_TRANSCRIPTS_DIR=~/.cursor/projects/Users-orosam-Projects-Termit/agent-transcripts \
  python3 scripts/rebuild_cursor_agent_context.py --project-root .
```

## Что создаётся (на проект)

| Артефакт | Путь |
|----------|------|
| Автосводка сессий | `.cursor/skills/termit-agent/archive/generated-from-transcripts.md` |
| Промпт нового агента (slug папки) | `.cursor/agent/projects/<slug>/new-agent-prompt.md` |
| Каноническая копия | `.cursor/NEW_AGENT_PROMPT.md` |

Для Termit `<slug>` = `termit`.

## Источники

- Parent-сессии: `~/.cursor/projects/<workspace-encoded>/agent-transcripts/*/UUID.jsonl` (без `subagents/`)
- Статический снимок: `archive/reference-sessions-baseline.md`
- Планы: `PROJECT_TASK_PROMPT_RU.md`, `reference.md`

## Правила

- Не править `generated-from-transcripts.md` вручную — только скриптом
- Subagent-транскрипты в сводку не входят
- Ответы агенту — на русском
