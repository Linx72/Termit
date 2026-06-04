# AutoCheckPoint — длинные чаты и память для агентов

## Зачем

В длинных диалогах Cursor **сжимает контекст** (`preCompact`). Без снимка теряются:

- что обсуждали и решили;
- какие файлы создали/меняли;
- на чём остановились.

**AutoCheckPoint** автоматически сохраняет компактный handoff в репозитории и подмешивает его агенту перед compaction и в новых сессиях.

## Как включить

1. В корне Termit уже есть [`.cursor/hooks.json`](../.cursor/hooks.json) — Cursor подхватывает при открытии проекта.
2. Перезапустите Cursor или сохраните `hooks.json` (hot reload).
3. Проверка: **Settings → Hooks** — должны быть `session_checkpoint.py` и `token_watch.py`.
4. Опционально: скопируйте [`.cursor/hooks/session_checkpoint.env.example`](../.cursor/hooks/session_checkpoint.env.example) → `session_checkpoint.env`.

## Порог 100 000 токенов

```env
TERMIT_CHECKPOINT_TOKEN_THRESHOLD=100000
```

- При **любом** `preCompact` пишется checkpoint + обновляется `ACTIVE.md`.
- В сообщении пользователю явно отмечается, если токенов **≥ 100k**.

## Где лежит память

| Путь | Назначение |
|------|------------|
| `.cursor/memory/ACTIVE.md` | Живая сводка для всех агентов |
| `.cursor/memory/checkpoints/*.md` | Снимки по событиям (compact / stop) |
| `.cursor/hooks/state/session_checkpoint.json` | Тех. учёт файлов/команд (локально) |

Правило для агента: [`.cursor/rules/session-memory.mdc`](../.cursor/rules/session-memory.mdc) (`alwaysApply: true`).

## События hooks

| Событие | Действие |
|---------|----------|
| `sessionStart` | В контекст подмешивается `ACTIVE.md` |
| `postToolUse` | Учёт путей файлов и shell-команд |
| `afterAgentResponse` | Краткие выдержки ответов |
| `preCompact` | Checkpoint + injection перед сжатием |
| `stop` | Финальный checkpoint |
| `subagentStart` | Тот же ACTIVE для subagent |

## Termit agents (API)

Для run'ов в Termit Desktop / API отдельно:

- `use_long_term_memory: true` в профиле агента;
- память в SQLite: `TERMIT_AGENT_MEMORY_*` в `.env`;
- `GET /api/agents/{agent_id}/memory`.

AutoCheckPoint дополняет Cursor-чаты; не заменяет Termit agent memory.

## Ручной compact

После очень длинной сессии можно дополнительно сказать в чате **«compact»** или использовать skill [compact-chat](https://github.com/douglac/compact-chat) для переноса в новый чат.

## Тесты

```bash
python3 -m unittest tests.test_session_checkpoint_hook tests.test_token_watch_hook -q
chmod +x .cursor/hooks/session_checkpoint.py .cursor/hooks/token_watch.py
```
