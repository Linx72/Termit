---
name: termit-agent
description: >-
  Termit project agent identity and workflows — local-first AI orchestrator with
  agent queue, tool loop 2.0, platform API (MCP/skills/hooks), eval/finetune, and
  Cursor-like clients. Use in Termit repo for agents, platform, finetune, eval,
  retrieval, clients, ops, or when the user says do all, Track B, platform
  parity, or asks what to build next.
---

# Termit Agent

## Identity

**One-liner:** локальный AI-оркестратор с очередью агентов, eval/finetune и Cursor-like клиентами. End-to-end, самопроверка, ответы на русском.

**Северная звезда:** Termit.app → репо → задача → агент читает код, правит, гоняет тесты, отчитывается без ручного копирования в чат.

## When to apply

- Любая задача в репозитории Termit
- Agent platform: tool loop, runs, queue, SSE, resume, confirm, multi-agent
- Platform layer: MCP, skills, hooks, guardrails, schedules, traces
- Context: retrieval, repo map, symbol index, context packing
- Finetune / eval / CI gate / training signals
- Clients: `termit-client`, `termit-desktop`, `vscode-extension`
- Prompts/skills: `data/prompts/`, `data/skills/`, `.cursor/skills/termit-prompts`
- «Do all», «do all automatic», «Track B», «platform parity», «что дальше», «на каком этапе»
- Автоматизация сервера, отключить scheduler/cron → skill **termit-automation**

## Master plan

| Документ | Назначение |
|----------|------------|
| [`PROJECT_TASK_PROMPT_RU.md`](../../../PROJECT_TASK_PROMPT_RU.md) | Фазы 0–5, Top 5, exit criteria |
| [`PLATFORM_PARITY_PLAN_RU.md`](../../../PLATFORM_PARITY_PLAN_RU.md) | Sprint A–D: Cursor/OpenAI/Antigravity parity |
| [`START_HERE_RU.md`](../../../START_HERE_RU.md) | Onboarding, LaunchAgent, Ollama, desktop |
| [`AUTOMATION_TASK_PROMPT_RU.md`](../../../AUTOMATION_TASK_PROMPT_RU.md) | do_all_automatic, toggles, `/api/ops/automation` |
| [`termit-automation`](../termit-automation/SKILL.md) | Skill: server automation + Desktop panel |

**Текущий вектор:** **0.4.1** — hosted beta smoke (`hosted_smoke.sh`), prod docker profile.

### Post-parity focus (закрыто в 0.3.6)

1. ~~Stability hardening~~ — unstable e2e nightly, SSE fallback
2. ~~Agent autonomy vNext~~ — outcome classes, policy fallback
3. ~~Desktop UX~~ — RuntimeStatusBar, Quick Start, DLQ, OpsSecurityPanel
4. ~~Eval/quality 2.0~~ — 74 scenarios, regression report, tiered gates
5. ~~Release discipline~~ — RELEASE_FLOW, release_pack, signed TermitShell.app

### Текущий фокус (0.4.1+)

1. Hosted beta: `./scripts/hosted_smoke.sh` через Caddy :8080
2. Prod docker profile (`docker-compose.prod.yml`, `deploy/docker.env.example`)
3. Media optional: Fal I2V / Lottie

Подробная карта: [reference.md](reference.md). Архив старых milestones: [archive/](archive/).

## Project map (quick)

| Область | Ключевые пути |
|---------|---------------|
| Wiring | `app/state.py`, `app/core/config.py`, `app/domain/schemas.py`, `app/main.py` |
| Agents / loop | `agent_service.py`, `agent_loop_service.py`, `multi_agent_orchestrator.py` |
| Platform | `app/api/routes/platform.py`, `agent_hook_service.py`, `mcp_registry_service.py`, `skill_store.py` |
| Projects | `app/api/routes/projects.py`, `project_rules_store.py`, `agent_templates_store.py` |
| Runs | `sqlite_agent_run_store.py`, `app/api/routes/agents.py` |
| Context | `repo_map_service.py`, `context_packing_service.py`, `symbol_index_service.py` |
| Routing | `model_router.py`, `routing_policy_service.py` |
| Finetune / eval | `finetune_*`, `eval_service.py`, `eval_ci_gate.py` |
| Clients | `clients/termit-client/src/agent.ts`, `clients/termit-desktop/` |
| Tests | `tests/test_phase1.py`, `test_phase2.py`, `test_platform_parity.py`, `test_platform_e2e.py` |

## Working style

1. Минимальный корректный diff; не трогать несвязанный код
2. «Do all» — блок целиком → тесты → smoke при runtime
3. Verify: `verify-after-serious-changes.mdc` — unittest + `:8765` + `scripts/smoke_http.sh`
4. Ответы на русском; код/коммиты — язык проекта
5. Итог: **passed/failed**, HTTP-коды, что не проверил

## Default workflows

### Backend / API

```
- [ ] Паттерны соседнего кода
- [ ] Правка
- [ ] python -m unittest discover -s tests -p 'test_<area>*.py' -q
- [ ] read_lints на затронутые файлы
- [ ] uvicorn :8765 + smoke (./scripts/smoke_http.sh или curl)
- [ ] Итог с фактами
```

### Agent run lifecycle

`queued → running → completed|failed|cancelled` (+ pause на `confirm`)

- SSE: `GET /api/agents/runs/{run_id}/stream`
- Resume: `POST .../resume`
- Risky tools: `POST .../confirm`
- SDK: `TermitAgent.create`, `agent.send`, `run.stream()`, `TermitAgent.resume`

### Platform / MCP / skills

- MCP registry + invoke: `/api/platform/mcp/*`
- Skills в продукте: `data/skills/`, API `/api/platform/skills`
- Hooks: `agent_hook_service.py`, preset `token_watch` в `.cursor/hooks/`

### Finetune / eval

- Signals: `data/finetune/training_signals.jsonl`
- CI gate: `scripts/eval_ci_gate.py`, `app/services/eval_ci_gate.py`
- Regression gate перед promote adapter
- Release gate: parity category `cursor_parity` минимум 20 сценариев (дальше расширять до 40+)

## Smoke

```bash
./scripts/smoke_http.sh
# или:
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/api/ops/readiness | head
```

Auth: `X-API-Key` из `.env` / `.env.example`.

## Anti-patterns

- «Перезапустите и проверьте» без своей проверки
- Переизобретать queue, SQLite runs, healthz, tool loop 2.0
- Большие рефакторинги без запроса
- «Должно работать» без прогона тестов
