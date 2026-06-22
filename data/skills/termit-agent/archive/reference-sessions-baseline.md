# Termit — справочник по архиву сессий (снимок)

> **Архив.** Актуальная версия: [`../reference.md`](../reference.md).

## Что уже сделано (milestones)

| Этап | Содержание |
|------|------------|
| Local runtime | Ollama/openai_compat status, models list, pull |
| Agent profiles | CRUD, registry (`data/agents.json`), run API |
| Run queue | Background workers, queued/running/completed/failed/cancelled |
| Persistence | SQLite agent runs, event timeline |
| Hardening | Retry, exponential backoff, dead-letter, failure_class |
| Observability | `/healthz`, Prometheus, alert thresholds, maintenance scheduler |
| Clients | TypeScript SDK, VS Code extension, desktop Monaco + inline edit |
| Eval MVP | Scenarios, reports, KPI |
| Finetune Stage1 | Export → job → adapter, dataset curation, regression gate |

## Архив чатов (источник промо)

- ~11 parent-сессий, ~250 user-запросов, 23 subagent-папки
- Типичные запросы: «do all», локальный ИИ, agent platform, Track B, bilingual UI, «проверяй сам»
- Частые файлы в сессиях: `schemas.py`, `state.py`, `agent_service.py`, `finetune_*`, `clients/termit-*`

## API surface (основное, до platform layer)

- Chat: `POST /api/chat`, `POST /api/chat/stream`
- Local: `GET /api/local/status`, `GET /api/local/models`, `POST /api/local/models/pull`
- Agents: `GET/POST /api/agents`, `POST /api/agents/{id}/runs`, `GET /api/agents/runs/{run_id}/events`
- Tools: `POST /api/tools/apply_patch`, agent-scoped tools under `/api/agents/{id}/tools/*`
- Ops: `GET /healthz`, `GET /api/metrics/prometheus`, `GET /api/ops/readiness`

## One-liner для новых чатов

> Termit-агент: локальный AI-оркестратор с очередью агентов, eval/finetune и Cursor-like клиентами. Делаю end-to-end, проверяю сам, отвечаю по-русски.
