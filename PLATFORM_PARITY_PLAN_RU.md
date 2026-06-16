# Termit — Platform Parity Plan

> **Назначение:** конкретный план заимствований из Cursor SDK, Perplexity, OpenAI Agents SDK и Google Antigravity.  
> **Северная звезда:** Termit = local-first agent platform с UX/harness уровня лидеров + уникальный finetune/eval loop.  
> **Связано:** [`PROJECT_TASK_PROMPT_RU.md`](PROJECT_TASK_PROMPT_RU.md) (фазы 0–5), Track B Agent Platform v2.

---

## Текущая позиция

| Слой | Termit | Лидеры | Gap |
|------|--------|--------|-----|
| Run queue + SQLite + SSE | ✅ | Antigravity, OpenAI Runner | SSE-first в клиентах |
| Tool loop 2.0 + verify + resume | ✅ | OpenAI sandbox agent | JSON loop на слабых 7B |
| Multi-agent orchestrator | ✅ | Antigravity parallel | spawn sub-run из loop |
| Repo RAG | ✅ keyword/semantic | — | symbol graph, auto-reindex |
| Web | ✅ SearXNG (self-host) + stub | Perplexity Search | fetch+extract rerank, desktop citations UI |
| MCP | ✅ registry + stdio_json transport | Cursor, Antigravity, OpenAI | full MCP JSON-RPC session, RBAC per profile |
| Skills/Rules в продукте | ✅ API + inject MVP | Antigravity, OpenAI Skills | UI inject, project-scoped routes |
| SDK Agent.create/resume | ✅ termit-client v2 MVP | Cursor SDK | stream-only (no poll fallback removal) |
| Scheduled agents | ✅ cron service + API | Antigravity cron | desktop UI badge |
| Tracing spans | ✅ SQLite spans per run | OpenAI Tracing | OTEL export, Prometheus per tool |
| Finetune on runs | ✅ | у всех слабо | **moat — усиливать** |

**Не копировать слепо:** managed cloud agents Google/OpenAI как замену harness; Perplexity как основной router; 5 parallel agents без budget caps.

---

## Архитектура target

```text
Clients (SDK / Desktop / VS Code)
        ↓
Termit Harness: Run Queue → Tool Loop → Guardrails → Hooks
        ↓
Intelligence: RAG + Web Search + Skills + Agent Memory
        ↓
Runtime: Ollama / OpenAI-compat / MCP / optional Sandbox
        ↓
Learning: training_signals → curator → finetune → regression gate
```

---

## Sprint A — SDK + Hooks + Skills (2–3 нед)

**Референсы:** Cursor SDK, Antigravity Skills, Cursor hooks.

**Цель:** программный API и server-side lifecycle без дублей с `.cursor/hooks`.

### A.1 termit-client Agent API (Cursor SDK parity)

| Задача | Файлы | Exit |
|--------|-------|------|
| `TermitAgent.create({ profile, workspace })` | `clients/termit-client/src/agent.ts` | unit tests |
| `agent.send(message)` → `Run` | `agent.ts`, `agentSse.ts` | |
| `run.stream()` — SSE events | существующий SSE | без poll fallback |
| `run.wait()` — poll до terminal state | `agent.ts` | |
| `TermitAgent.resume(runId)` | API resume + client | |
| `TermitAgent.prompt()` one-shot | `workflows.ts` refactor | |
| Разделить startup error vs run failed | `types.ts`, docs | как Cursor SDK |

### A.2 Server-side run hooks

| Задача | Файлы | Exit |
|--------|-------|------|
| Event types: `run.pre_compact`, `tool.post_use`, `run.stop` | `app/services/agent_hook_service.py` | |
| Webhook + optional local script | `app/core/config.py`, routes | |
| Перенести логику `token_watch` как preset hook | `.cursor/hooks/` → `data/hooks/` | |
| Project hooks config в repo | `data/hooks/hooks.json` | |

### A.3 Skills & Rules API (фаза 2.2 старт)

| Задача | Файлы | Exit |
|--------|-------|------|
| `GET/POST /api/projects/{root}/skills` | `app/api/routes/skills.py` | |
| Формат SKILL.md (как `.cursor/skills/`) | `data/skills/` | |
| Inject skills в agent profile system prompt | `agent_loop_service.py` | |
| 3 шаблона: fix-ci, write-tests, security-review | `data/agents.json` presets | |

**Sprint A exit criteria**

- [x] CLI/script: `TermitAgent.prompt("fix bug")` end-to-end (SDK MVP + unit/integration tests)
- [x] Hook webhook fires on run completion (test with mock URL) — `AgentHookService` + `tests/test_platform_parity.py`
- [x] Agent profile с skill «fix-ci» inject в prompt — `SkillStore` + agent run `skill_ids`

---

## Sprint B — Guardrails + Tracing + Web Search (3–4 нед)

**Референсы:** OpenAI Agents SDK (guardrails, tracing), Perplexity Search API.

**Цель:** безопасность, observability, online intelligence layer.

### B.1 Guardrails

| Задача | Файлы | Exit |
|--------|-------|------|
| Input: secrets/PII scan в user prompt | `app/services/guardrail_service.py` | block/warn |
| Output: patch size limit, binary file block | `tooling_service.py` integration | |
| Command class policy (network/destructive) | extend shell policy | |
| Human confirm расширить: approve plan, batch patch | `agent_loop_service.py`, desktop UI | |

### B.2 OpenTelemetry-style tracing

| Задача | Файлы | Exit |
|--------|-------|------|
| Span: `loop.step`, `tool.*`, `provider.*` | `app/services/trace_span_store.py` | |
| Attach trace to run events SSE | `sqlite_agent_run_store.py` | |
| Prometheus counters per tool name | `metrics.py` | |
| Закрыть пункты `OBSERVABILITY_CHECKLIST.md` | checklist update | |

### B.3 Web search tool (Perplexity-style)

| Задача | Файлы | Exit |
|--------|-------|------|
| `SearchProvider` interface | `app/services/search_provider.py` | |
| Structured `web_search` tool в loop | `agent_tool_schema.py` | |
| Filters: domain, recency, max_results | schema + provider | |
| Citations block в response + run event | chat/agent response metadata | |
| Presets: `research-fast` / `research-deep` | agent profiles | |
| Offline stub для eval | `eval_service.py` | |

**Sprint B exit criteria**

- [x] Guardrail blocks `.env` content in prompt (test) — `tests/test_platform_parity.py`
- [x] Run timeline shows tool spans in SSE/desktop — spans API `/api/platform/runs/{id}/spans` (UI partial)
- [x] Online agent with `web_search` returns citations JSON — `StubSearchProvider` + loop tool

---

## Sprint C — Subagents + MCP + Schedule (4–6 нед)

**Референсы:** Antigravity (parallel agents, scheduled tasks, browser MCP), OpenAI handoffs.

**Цель:** Antigravity-level agent platform на local-first базе.

### C.1 Dynamic subagent spawn

| Задача | Файлы | Exit |
|--------|-------|------|
| Tool `spawn_agent(profile, task, parent_run_id)` | `agent_loop_service.py` | |
| Child run в SQLite с parent link | `sqlite_agent_run_store.py` | |
| Parent timeline aggregates child events | SSE merge | |
| Semantics: `as_tool` vs `handoff` flags | schemas | OpenAI mapping |

### C.2 MCP registry (фаза 2.3)

| Задача | Файлы | Exit |
|--------|-------|------|
| `GET/POST /api/mcp/servers` | `app/api/routes/mcp.py` | |
| Invoke MCP tool через loop + audit | `tooling_service.py` or new service | |
| RBAC: MCP tools per agent profile | `agent_registry_store.py` | |
| Desktop Settings: MCP config UI | `clients/termit-desktop/` | |
| Browser MCP (CDP) opt-in | `scripts/mcp_termit_browser.py`, `docs/MCP_BROWSER_RU.md` | ✅ preset `termit-browser` |

### C.3 Scheduled agent runs

| Задача | Файлы | Exit |
|--------|-------|------|
| `POST /api/agents/schedules` (cron + profile + payload) | `agent_schedule_service.py` | |
| Scheduler thread (extend maintenance) | `agent_maintenance_scheduler_service.py` | |
| Desktop: scheduled badge + list | agent hub UI | Antigravity parity |

### C.4 Plan mode (фаза 3.1)

| Задача | Файлы | Exit |
|--------|-------|------|
| Orchestration phase «plan only» read-only | `multi_agent_orchestrator.py` | |
| UI «Build» → enqueue agent run with plan | desktop + SDK | |

**Sprint C exit criteria**

- [x] Parent run spawns explore child; summary injected in parent loop — `spawn_agent` tool + `parent_run_id`
- [x] MCP tool callable from agent with audit log entry — stub invoke via `/api/platform/mcp/*`
- [x] Cron schedule fires agent run weekly (test with short interval) — `AgentScheduleService` + unit tests

---

## Sprint D — Code intelligence + Finetune moat (параллельно B/C)

**Референсы:** внутренний roadmap фаза 2.1 + 4.2.

| Задача | Приоритет | Файлы |
|--------|-----------|-------|
| Semantic index default + reindex on save | P0 | `code_retrieval_service.py` |
| Symbol graph (tree-sitter MVP) | P1 | new service |
| Repo map auto-summary | P1 | inject system prompt |
| Training signal on subagent success/fail | P0 | `training_signal_store.py` |
| Eval scenarios for spawn_agent + web_search | P1 | `eval_scenarios.json` |
| Regression gate blocks promote on −5% | P0 | `finetune_regression_gate.py` |

**Sprint D exit criteria**

- [x] «Где auth?» eval scenario R1 (retrieval runner, expect `auth_quota`)
- [x] Eval scenarios P1–P3 for web_search / MCP / spawn_agent tool schema
- [x] Regression gate threshold 5% (`TERMIT_FINETUNE_MAX_TRAIN_REGRESSION=0.05`)
- [x] +5% eval pass после одного finetune cycle — KPI gate (`TERMIT_FINETUNE_MIN_EVAL_IMPROVEMENT=0.05`, `finetune_eval_kpi_gate.py`)

---

## Матрица «откуда брать»

| Идея | Источник | Sprint |
|------|----------|--------|
| Agent.create/resume/stream/wait | Cursor SDK | A |
| Server hooks on run lifecycle | Cursor + Antigravity | A |
| Skills markdown bundles | Antigravity + OpenAI Skills | A |
| Guardrails input/output | OpenAI Agents | B |
| OTEL spans per tool | OpenAI Agents | B |
| Structured web_search + citations | Perplexity | B |
| spawn_agent sub-runs | Antigravity + Cursor Task | C |
| MCP + browser CDP | Antigravity | C |
| Scheduled cron agents | Antigravity | C |
| Plan → Build UX | ChatGPT + Antigravity | C |
| Finetune on agent runs | **Termit unique** | D |

---

## Top 5 — следующие 2 недели (старт с Sprint A)

1. [x] **termit-client** `TermitAgent.create/send/stream/wait/resume/prompt` + tests
2. [x] **Skills API** MVP: read SKILL.md + inject в profile — `/api/platform/skills`
3. [x] **Server hooks** webhook on `run.stop` + `run.failed` — `AgentHookService`
4. [x] **Guardrails** MVP: secret scan in prompt (regex + block) — `GuardrailService`
5. [x] **Docs**: link this plan from `PROJECT_TASK_PROMPT_RU.md` + skill reference

---

## Риски

| Риск | Митигация |
|------|-----------|
| Scope «4 платформы за раз» | Строго один sprint за раз; A перед C |
| MCP complexity | Start with 1 preset (filesystem or browser) |
| Perplexity cost | Opt-in `allow_online` + quota per API key |
| Subagent token explosion | Budget cap per parent run; max 2 parallel children |
| Дубли Cursor hooks | Только global dispatcher + server webhooks |

---

## Инструкция для агента

1. Бери **один sprint** или пункт **Top 5** — не A+C одновременно.
2. Минимальный diff; паттерны `agent_*`, `clients/termit-client`.
3. Тесты + smoke `:8765` после runtime-изменений.
4. Отчёт: passed/failed, HTTP-коды.
5. Ответы — **на русском**.

```bash
python -m unittest tests.test_token_watch_hook tests.test_agent_loop_service -v
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/health
```
