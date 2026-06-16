# Termit — промпт задачи: полноценный ИИ и приложение

> **Назначение:** мастер-план для агентов и разработчиков. При запросах «do all», «Track B», «что дальше», «полноценный ИИ» — следовать этому документу.
>
> **Северная звезда:** пользователь открывает Termit.app → выбирает репо → ставит задачу → агент сам читает код, правит, гоняет тесты, отчитывается — без ручного копирования в чат.

**Связанные документы:** `ROADMAP_90_DAYS.md`, `Q2_ROADMAP.md`, `SPRINT_BACKLOG.md`, [`PLATFORM_PARITY_PLAN_RU.md`](PLATFORM_PARITY_PLAN_RU.md) (Cursor/Perplexity/OpenAI/Antigravity → Termit), `.cursor/skills/termit-agent/SKILL.md`

---

## Текущее состояние (baseline)

| Есть | Не хватает для «полноценного» |
|------|-------------------------------|
| FastAPI, chat/stream, routing, RAG | Надёжный autonomous agent loop на слабых локальных моделях |
| Tool loop (JSON action → tool → observe) | Native function calling, resume, subagents |
| Очередь run'ов, SQLite, SSE timeline | Единый real-time UX без polling |
| Composer, ⌘K, tab completion | Качество и скорость на уровне коммерческих IDE |
| Eval (53 сценария), finetune stage 1 | Замкнутый цикл «ошибка → обучение → regression gate → promote» |
| Desktop + VS Code + SDK | Один polished primary client, onboarding «из коробки» |

**Приоритет Track B:** Agent Platform v2 — не «только finetune», а tool loop, multi-agent, routing policy, обучение на agent-run сигналах.

---

## Фаза 0 — Стабилизация базы (2–3 недели)

**Цель:** не строить новое, пока текущее не держит daily use.

### Backlog

- [x] Единый smoke-контур: автотест + curl на `:8765` после runtime-изменений
- [x] CI: `unittest` + lint + минимальный e2e (chat → apply_patch → agent run)
- [x] Улучшить парсинг JSON-действий в tool loop (`tool_json_parser`) — fallback, repair, few-shot в system prompt
- [x] Метрики tool loop: % успешных tool steps, % run'ов до `final` без timeout
- [x] VS Code Agents tab: SSE вместо poll ~2s → `GET /api/agents/runs/{id}/stream`
- [x] Desktop: тот же SSE-first для agent timeline
- [x] Документировать путь «первый успешный Composer run за 10 минут» в `START_HERE_RU.md`

### Ключевые файлы

- `app/services/agent_loop_service.py`, `app/services/tool_json_parser.py`
- `clients/vscode-extension/`, `clients/termit-desktop/`
- `tests/test_agent_loop_service.py`, `tests/test_*_api_e2e.py`

### Exit criteria

- 5 типовых задач (fix bug, add test, refactor file, explain code, multi-file feature) проходят end-to-end без ручного вмешательства в **≥60%** случаев

---

## Фаза 1 — Agent Platform v2 (4–6 недель)

**Цель:** ядро «полноценного ИИ».

### 1.1 Tool loop 2.0

```
User task → Planner (optional) → Loop: think → tool → observe → … → verify → report
```

- [x] Structured tool schema: OpenAI-style `tools[]` + native function calling для compat-провайдеров; JSON-loop как fallback для Ollama
- [x] Step budget & anti-loop: динамический лимит шагов, детекция повторов, эскалация к stronger model
- [x] Verify phase: auto `pytest`/`npm test` по heuristics репо; fail → retry с контекстом ошибки
- [x] Run resume: checkpoint в SQLite — `POST /api/agents/runs/{id}/resume`
- [x] Human-in-the-loop: пауза на `confirm` для risky tools; UI «Approve / Reject» в desktop

### 1.2 Multi-agent orchestration

Уже есть `MultiAgentOrchestrator` — довести до продукта:

- [x] Planner → декомпозиция задачи
- [x] Coder → правки через tools
- [x] Reviewer → read-only review + suggestions
- [x] Verifier → tests/lint
- [x] Параллельные subagent'ы для explore (search codebase + read files concurrently)

**Файлы:** `app/services/multi_agent_orchestrator.py`, `app/api/routes/orchestration.py`

### 1.3 Routing policy 2.0

- [x] Профили моделей per repo / per task type (`coding-fast`, `coding-strong`, `review`)
- [x] Dual-pass по умолчанию для `coding`: draft (7B) + validator (32B или cloud)
- [x] Budget-aware routing: latency/cost caps в `.env` (`TERMIT_ROUTING_MAX_CANDIDATES`)

**Файлы:** `app/services/model_router.py`, `app/state.py`

### 1.4 Agent memory

- [x] Долгая память агента: факты о репо, решения, стиль — SQLite/JSONL, inject в loop
- [x] Session + project scope: `workspace_scope` / `retrieval_path_prefix`

### Exit criteria

- Agent run с `use_tool_loop=true` завершает eval-сценарии с patch + test verify
- SSE timeline показывает каждый шаг в desktop

---

## Фаза 2 — Интеллект и контекст (4–5 недель)

**Цель:** локальные модели работают за счёт контекста, не только размера модели.

### 2.1 Code intelligence

- [x] Hybrid retrieval by default (`TERMIT_RETRIEVAL_MODE=hybrid`), manual reindex в UI
- [x] Symbol graph (MVP): Python AST call edges + callers/callees в `/api/retrieval/symbols/search`
- [x] Context packing: changed files + retrieval + dependency neighbors
- [x] Repo map: авто-summary структуры проекта для system prompt
- [x] Lightweight symbol index (Python AST + TS/JS regex) + `/api/retrieval/symbols/*`

**Файлы:** `app/services/repo_map_service.py`, `app/services/context_packing_service.py`, `app/services/context_enrichment_service.py`

### 2.2 Skills & Rules в продукте

Сейчас rules/skills в `.cursor/` — перенести в Termit:

- [x] UI: project rules + user rules в desktop sidebar (skills — через platform API)
- [x] API: `GET/POST /api/projects/{id}/rules`, inject в chat/agent prompts
- [x] Шаблоны агентов: «fix CI», «write tests», «security review»

**Файлы:** `data/agent_templates.json`, `app/services/project_rules_store.py`, `app/api/routes/projects.py`

### 2.3 MCP как first-class

- [x] MCP server registry в backend (`/api/platform/mcp/*`)
- [x] Агент вызывает MCP tools через RBAC/audit (`mcp_invoke`)
- [x] Desktop: настройка MCP в Settings (add/list servers)

### Exit criteria

- Запрос «где обрабатывается auth?» находит правильные файлы в **≥80%** случаев
- @codebase даёт релевантный контекст без ручного @file

---

## Фаза 3 — Приложение Termit (6–8 недель)

**Цель:** один primary client (desktop); VS Code — thin extension поверх SDK.

### 3.1 UX parity с Cursor (must-have)

| Фича | Статус | Доработка |
|------|--------|-----------|
| Chat + stream | ✓ | Rename, search history ✓ |
| Composer multi-file | ✓ | Partial apply ✓, undo stack ✓ |
| Inline edit ⌘K | ✓ | Быстрее, preview inline в Monaco |
| Tab completion | ✓ | Debounce, cache, accept-word/line |
| Agent runs timeline | ✓ | Live SSE, expandable tool I/O |
| @ context | ✓ | @folder, @symbol, @docs, @web |
| Plan mode | ✓ | Plan tab → Build → Composer |
| Terminal integration | ✓ | Terminal tab (execute_command + history) |

**Файлы:** `clients/termit-desktop/`, `clients/termit-client/`, `clients/CLIENT_UX.md`

### 3.2 Onboarding & settings

- [x] Wizard: Ollama pull models step + connect + workspace
- [x] Model manager UI: pull missing models в sidebar
- [x] Health dashboard в sidebar: queue, index, readiness

### 3.3 Workspace UX

- [x] File tree (Editor) + git changed files panel в sidebar
- [x] Composer partial apply per patch + rollback
- [x] Bilingual RU/EN — locale toggle + i18n для новых панелей

### 3.4 Web (optional, позже)

- [x] Web UI на `/` — chat, agents, eval KPI dashboard, finetune ops

### Exit criteria

- Новый пользователь без README проходит onboarding и делает первый Composer apply за один сеанс

---

## Фаза 4 — Качество и обучение (4–6 недель, параллельно)

**Finetune — усилитель платформы, не замена.**

### 4.1 Eval 2.0

- [x] Расширить `data/eval_scenarios.json`: patch quality, tool selection, multi-step, cross-platform X1–X4 (53 сценария, runner `tool_sequence`)
- [x] Cross-platform atomic dev: `/api/dev/cross-platform/*`, agent templates + skill, SDK `runAtomicDevWorkflow`, eval runner `cross_platform_decompose`
- [x] KPI dashboard в UI: success rate, latency p95, cost/run (desktop HealthDashboard + `/api/finetune/training/dashboard`)
- [x] Regression gate перед каждым release и promote adapter (CI eval + gate в finetune pipeline)

**Файлы:** `app/services/eval_service.py`, `app/services/agent_eval_service.py`, `data/eval_scenarios.json`

### 4.2 Training loop

```
Agent runs (success/fail) → training_signals.jsonl → curator → dataset → finetune job → adapter
```

- [x] Успешный patch + green tests → SFT example (`try_capture_tool_step` verified + export)
- [x] User revert / edit after apply → DPO / negative (`PatchOutcomeStore`)
- [x] Tool loop failures → prompt/tool schema tuning (`tool_loop_tuning_service`, dashboard `tuning_report`)

**Файлы:** `app/services/finetune_dataset_curator.py`, `app/services/finetune_service.py`, `app/services/finetune_trainer_service.py`, `data/finetune/`, `scripts/training_loop_week2.sh`

### 4.3 Model profiles per repo

- [x] `data/finetune/adapters/{repo}/` — локальный LoRA под стиль проекта (FS fallback + registry)
- [x] Router: если есть adapter для repo → использовать (`FinetuneAdapterResolver` + auto-sync on promote)

### Exit criteria

- Measurable **+5–10%** eval pass rate после одного цикла finetune
- Gate блокирует регрессии

---

## Фаза 5 — Production & scale (4+ недель)

- [ ] Docker compose prod, systemd/LaunchAgent polish, backup SQLite
- [ ] UI для API keys, team quotas, audit export (RBAC уже есть)
- [ ] Grafana dashboard из Prometheus; alert на failed runs spike
- [ ] Graceful shutdown workers, dead-letter queue UI, run retry policies
- [ ] Secret scan in patches, sandbox hardening, signed desktop builds

### KPI targets

| Метрика | Цель |
|---------|------|
| Task Success Rate | ≥ 75% |
| p95 TTFT | < 3s (fast model) |
| Automation Rate | ≥ 60% |
| Service uptime | ≥ 99.5% |
| D30 retention (beta) | ≥ 35% |

---

## Следующий этап после parity-релиза 0.3.4 (4–8 недель)

**Цель этапа:** перейти от parity к устойчивому production-режиму: меньше флейков, выше автономность run, предсказуемые релизы и измеримая пользовательская ценность.

### Трек 1 — Stability hardening (недели 1–2)

- [x] Закрыть источники `ResourceWarning` (unclosed sqlite connections) в runtime и тестах
- [ ] Дожать флейки e2e для фоновых run (`running -> completed`)
- [ ] Разделить unstable integration тесты в nightly-контур

**DoD:** 20 последовательных прогонов smoke/release smoke без критичных флейков.

### Трек 2 — Agent autonomy vNext (недели 2–4)

- [ ] Усилить stop-conditions и recovery path в tool loop при деградации
- [ ] Добавить policy-level fallback (constrained-plan + safe-exec)
- [ ] Ввести явные outcome classes: success / partial / blocked-external / blocked-policy

**DoD:** рост completion-rate и снижение repeat/empty-final кейсов на типовых coding run.

### Трек 3 — Desktop product UX (недели 3–5)

- [ ] Улучшить post-run follow-up в стиле next best action
- [ ] Довести onboarding до first-run за < 2 минут
- [ ] Вывести runtime status в UI (SLA, retries, active runs)

**DoD:** P95 до первого осмысленного шага остаётся < 5s в реальном использовании.

### Трек 4 — Eval/quality 2.0 (недели 4–6)

- [ ] Расширить parity-сценарии до 40+ (сложные multi-file/multi-step кейсы)
- [ ] Развести quality gates: fast (PR), deep (nightly), release (обязательный)
- [ ] Автоматизировать отчёт деградаций относительно предыдущего релиза

**DoD:** каждый релиз проходит release gate; каждая регрессия имеет сценарий воспроизведения.

### Трек 5 — Release discipline & ops (недели 5–8)

- [ ] Формализовать поток `rc -> stable -> hotfix`
- [ ] Автоматизировать пакет `changelog + migration notes + rollback`
- [ ] Закрыть операционные SLO/SLA-дашборды и алерты

**DoD:** релиз выполняется одной командой без ручных патчей скриптов.

### Следующий спринт (5–7 дней, immediate)

1. [x] Убрать unclosed sqlite warnings
2. [x] Стабилизировать `test_platform_e2e`/`test_agents_api` без тайминговых флейков
3. [x] Разделить release smoke на deterministic core и extended suite
4. [x] Добавить lifecycle summary в UI (completion/timeout/stale)
5. [ ] Подготовить и выпустить `0.3.5` как stability release

---

## Порядок выполнения

```text
Фаза 0 (стабильность)
    ↓
Фаза 1 (Agent v2) ──→ Фаза 3 (desktop UX)
    ↓                      ↓
Фаза 2 (контекст) ──→ Фаза 4 (eval/finetune)
                            ↓
                      Фаза 5 (production)
```

---

## Top 5 — ближайший спринт (2 недели)

1. [x] Tool loop reliability + verify-after-patch (tests)
2. [x] SSE everywhere в клиентах (убрать polling)
3. [x] Semantic retrieval by default + auto-reindex hook
4. [x] Agent run resume + human confirm для risky tools
5. [x] Eval gate в CI + dashboard pass rate

---

## Риски и митигации

| Риск | Митигация |
|------|-----------|
| Слабые локальные 7B ломают JSON loop | Dual-pass, stronger validator, native function calling |
| Scope creep «как Cursor за 3 месяца» | Один primary client (desktop), VS Code = SDK consumer |
| Finetune без данных | Сначала logging runs + curator; finetune при N>500 сигналов |
| Безопасность tools | Не ослаблять policy; human-in-the-loop для confirm |

---

## Инструкция для агента

При работе по этому промпту:

1. Выбери **одну фазу** или пункт из **Top 5** — не распыляйся.
2. Минимальный diff, существующие паттерны проекта (`agent_*`, `finetune_*`, `clients/termit-*`).
3. После правок: `python -m unittest discover -s tests` (релевантные модули) + smoke `:8765`.
4. Отчёт: passed/failed, HTTP-коды, что не проверил.
5. Ответы пользователю — **на русском**.

### Smoke commands

```bash
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/healthz | head
curl -s http://127.0.0.1:8765/api/metrics/thresholds | head
curl -s http://127.0.0.1:8765/api/ops/readiness | head
```

Auth: `X-API-Key` из `.env` / `.env.example` (`dev-key`, `viewer-key`).
