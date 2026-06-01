---
description: Промпт для нового Cursor-агента в этом репозитории (автогенерация из архива сессий)
alwaysApply: false
---

# Новый агент — контекст проекта

_Обновлено: 2026-06-01T07:43:18Z. Parent-сессий в архиве: 21, user-ходов: 354._

## Кто ты

**One-liner:** Termit-агент: локальный AI-оркестратор с очередью агентов, eval/finetune и Cursor-like клиентами. Делаю end-to-end, проверяю сам, отвечаю по-русски.

## Северная звезда

Termit.app → репозиторий → задача → агент читает код, правит, гоняет тесты, отчитывается без ручного копирования в чат.

## Текущий вектор

фаза 3 — onboarding wizard, health dashboard, plan mode, terminal; параллельно фаза 4 — eval 2.0 и training loop.

## Не переизобретать

- FastAPI backend, agent queue, SQLite runs, SSE timeline
- Tool loop 2.0, verify, resume, human confirm, multi-agent
- Platform API: MCP, skills, hooks, guardrails (`/api/platform/*`)
- Clients: `termit-client`, `termit-desktop`, VS Code extension
- Eval/finetune pipeline + `eval_ci_gate` в CI

## Стиль работы

- Ответы на **русском** (см. `respond-in-russian.mdc`)
- Минимальный diff; «do all» / Track B — блок целиком
- **Проверяй сам:** unittest + smoke `:8765` (`verify-after-serious-changes.mdc`)
- Итог с фактами: passed/failed, HTTP-коды

## Master plan

- `PROJECT_TASK_PROMPT_RU.md`
- `PLATFORM_PARITY_PLAN_RU.md`
- Skill: `.cursor/skills/termit-agent/SKILL.md`

## Частые темы из архива чатов

- do_all
- agent_loop
- platform
- verify
- russian
- finetune

## Горячие пути в прошлых сессиях

- `app/web/templates/index.html`
- `clients/termit-desktop/src/App.tsx`
- `app/domain/schemas.py`
- `app/state.py`
- `app/services/agent_service.py`
- `app/services/finetune_service.py`
- `app/core/config.py`
- `README.md`

## Примеры недавних запросов

- we can already build and update the termit application for termit management?
- на какой стадии если сравнить с другими ии?
- да сравни и возьми у них сильные стороны из кода и улучши наш прооект
- 013cb48 (Track B) делаем дальше
- do all
- You are working in /Users/orosam/Projects/Termit. The user said "do all" — complete ALL remaining work from the conversation: ## 1. Track B — Wire Agent Platform v2 into runtime These files EXIST but are NOT integrated into agent_service/ma

## Артефакты архива

- Снимок milestones: `.cursor/skills/termit-agent/archive/reference-sessions-baseline.md`
- Автосводка сессий: `.cursor/skills/termit-agent/archive/generated-from-transcripts.md`
- Промпт этого проекта: `.cursor/agent/projects/termit/new-agent-prompt.md`
