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

- [x] Docker compose prod, systemd/LaunchAgent polish, backup SQLite — `docker-compose.prod.yml`, `scripts/backup_sqlite.sh`
- [x] UI для API keys, team quotas, audit export (RBAC уже есть) — `OpsSecurityPanel` в desktop
- [x] Graceful shutdown workers, run retry policies — `TERMIT_AGENT_SHUTDOWN_GRACE_SECONDS`, `/api/ops/runtime-policy`
- [x] Dead-letter queue UI — DLQ list/replay в desktop `AgentObservabilityPanel`
- [x] Secret scan in patches — `GuardrailService.check_patch_content`
- [x] Signed desktop builds, sandbox hardening (extended) — `TermitShell.app` codesign/notary, `docs/DESKTOP_SIGNING_RU.md`, release workflow

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
- [x] Дожать флейки e2e для фоновых run (`running -> completed`) — unstable suites в nightly, SSE fallback в PR
- [x] Разделить unstable integration тесты в nightly-контур

**DoD:** 20 последовательных прогонов smoke/release smoke без критичных флейков.

### Трек 2 — Agent autonomy vNext (недели 2–4)

- [x] Усилить stop-conditions и recovery path в tool loop при деградации — typed `failure_class` на AgentLoopError
- [x] Добавить policy-level fallback (constrained-plan + safe-exec)
- [x] Ввести явные outcome classes: success / partial / blocked-external / blocked-policy

**DoD:** рост completion-rate и снижение repeat/empty-final кейсов на типовых coding run.

### Трек 3 — Desktop product UX (недели 3–5)

- [x] Улучшить post-run follow-up в стиле next best action — outcome-aware suggestions в desktop
- [x] Довести onboarding до first-run за < 2 минут — wizard Quick Start + optional Ollama
- [x] Вывести runtime status в UI (SLA, retries, active runs) — RuntimeStatusBar + HealthDashboard в desktop

**DoD:** P95 до первого осмысленного шага остаётся < 5s в реальном использовании.

### Трек 4 — Eval/quality 2.0 (недели 4–6)

- [x] Расширить parity-сценарии до 40+ (сложные multi-file/multi-step кейсы)
- [x] Развести quality gates: fast (PR), deep (nightly), release (local/manual с cloud judge)
- [x] Автоматизировать отчёт деградаций относительно предыдущего релиза — `scripts/eval_regression_report.py`

**DoD:** каждый релиз проходит release gate; каждая регрессия имеет сценарий воспроизведения.

### Трек 5 — Release discipline & ops (недели 5–8)

- [x] Формализовать поток `rc -> stable -> hotfix` — `docs/RELEASE_FLOW.md`
- [x] Автоматизировать пакет `changelog + migration notes + rollback` — `scripts/release_pack.sh`
- [x] Закрыть операционные SLO/SLA-дашборды и алерты — Prometheus rules + Grafana Termit SLO

**DoD:** релиз выполняется одной командой без ручных патчей скриптов.

### Следующий спринт (5–7 дней, immediate)

1. [x] Убрать unclosed sqlite warnings
2. [x] Стабилизировать `test_platform_e2e`/`test_agents_api` без тайминговых флейков
3. [x] Разделить release smoke на deterministic core и extended suite
4. [x] Добавить lifecycle summary в UI (completion/timeout/stale)
5. [x] Подготовить и выпустить `0.3.5` как stability release

### Следующий этап (0.3.7): Finetune loop closure

- [x] Единый скрипт `training_loop_full.sh` (signals → train → eval → regression)
- [x] Документация `docs/FINETUNE_LOOP_RU.md`
- [x] Автоматический weekly cron: `training_loop_weekly.sh` + baseline promote (`eval_baseline_promote.py`)
- [x] Provider/cost observability — fallback rate, cost/task, model_usage в Prometheus + alert
- [x] Измерить +5% eval pass после одного stage1 cycle — KPI gate `finetune_eval_kpi_gate.py` в `stage1_full_loop.sh` / `training_loop_full.sh` (фактическое значение фиксируется при train+eval прогоне)

**DoD:** один командный прогон `./scripts/training_loop_full.sh` закрывает цикл без ручных шагов; promote/shadow по regression gate.

### Следующий этап (0.3.8): Desktop North Star + observability polish

- [x] Подключить `WorkflowHubPanel` + `KpiGatePanel` в desktop settings (North Star journeys + KPI gates)
- [x] Eval pass rate by scenario category в dashboard + Prometheus (`termit_eval_pass_rate_by_category`)
- [x] Исправить Prometheus alerts (WorkersDown + provider failure burst)

**DoD:** в настройках desktop видны journeys и KPI gates; `/api/metrics/prometheus` экспортирует eval по категориям.

### Следующий этап (0.3.9): Observability + Media Studio polish

- [x] Structured JSON logs (`TERMIT_LOG_JSON`) + redaction policy
- [x] Trace spans: `provider.*`, `verify.stage`, `verify.pass/failed/retry`
- [x] Media Studio human-approve gate в Desktop (HTTP 428 → confirm UI)
- [x] Error logs with stable `error_class` in JSON formatter

**DoD:** JSON logs без секретов; agent run spans покрывают provider+verify; paid media требует confirm в UI.

### Следующий этап (0.4.0): Team online + OTEL spans

- [x] OTEL export spans: `GET /api/platform/runs/{run_id}/spans/otel`
- [x] Media tool trace spans (`media.generate_image`, `media.run_storyboard`) в TraceSpanStore
- [x] Desktop `OnlineAcceleratorPanel` — shared runs + heavy eval jobs в settings

**DoD:** spans экспортируются в OTEL JSON; media ops пишут spans при `run_id`; team share доступен из desktop.

### Следующий этап (0.4.1): Hosted beta hardening

- [x] `scripts/hosted_smoke.sh` — smoke через Caddy :8080 + trace header + optional auth gate
- [x] Документация: `HOSTED_DEPLOYMENT.md`, `deploy/docker.env.example`, `BETA_ONBOARDING.md`
- [x] `release_all.sh` — ссылка на hosted smoke

**DoD:** после `docker compose up` один прогон `./scripts/hosted_smoke.sh` зелёный; auth profile проверяется с `TERMIT_HOSTED_AUTH_EXPECT=true`.

### Следующий этап (0.4.2): Media Studio Fal I2V + Lottie

- [x] Fal I2V: `TERMIT_MEDIA_PUBLIC_BASE_URL` или upload в fal CDN (`FalVideoProvider.upload_local_image`)
- [x] `POST /api/media/export-lottie` + agent tool `export_lottie`
- [x] Desktop Media Studio: кнопка «Экспорт Lottie»

**DoD:** `render_video` с `provider=fal` работает при `FAL_KEY` + public URL или CDN upload; Lottie JSON из PNG sequence; тесты `test_media_jobs` зелёные.

### Следующий этап (0.4.3): Media observability + hosted media smoke

- [x] Trace spans: `media.render_video`, `media.export_gif`, `media.export_lottie`
- [x] Eval MS11 — Lottie export scenario
- [x] `hosted_smoke.sh` optional media gate (`TERMIT_HOSTED_MEDIA_EXPECT=true`)
- [x] `deploy/docker.env.example` — Media Studio env block

**DoD:** media ops пишут spans при `run_id`; MS11 passed; hosted smoke с media gate зелёный при `TERMIT_MEDIA_ENABLED=true`.

### Следующий этап (0.4.4): Product KPI targets (Phase 5)

- [x] North Star KPI gates: task success ≥75%, automation ≥60%, chat p95 TTFT <3s
- [x] Prometheus: `termit_automation_rate`, `termit_desktop_kpi_gates_passed`, task counters
- [x] Desktop `KpiGatePanel` — корректный формат ms/s для latency gates
- [x] `hosted_smoke.sh` — проверка `/api/desktop/kpi-gates`

**DoD:** `/api/desktop/kpi-gates` включает product KPI при наличии telemetry; Prometheus экспортирует automation + KPI gate status.

### Следующий этап (0.4.5): Beta growth — D30 retention + feedback

- [x] `BetaCohortService` — D7/D30 retention из feedback + tasks + agent runs
- [x] `GET /api/ops/beta-metrics`, `GET /api/feedback/summary`
- [x] Desktop `BetaFeedbackPanel` + `feedbackOps.ts`
- [x] KPI gate `d30_retention_min` (≥35%, cohort ≥5)

**DoD:** beta metrics доступны из API; feedback из desktop; Prometheus `termit_beta_d30_retention_rate`.

### Следующий этап (0.4.6): Beta growth dashboard — web + HealthDashboard

- [x] Web UI: beta KPI grid (`/api/ops/beta-metrics`, `/api/feedback/summary`)
- [x] Desktop `HealthDashboard` — D30/D7 retention, active users, feedback count
- [x] `export_kpi_dashboard.py` — beta_metrics, feedback_summary, kpi_gates

**DoD:** beta growth виден в web ops и HealthDashboard; KPI export bundle включает beta cohort.

### Следующий этап (0.4.7): Browser MCP preset (Playwright bridge)

- [x] `scripts/mcp_termit_browser.py` — MCP stdio server (navigate/snapshot/click)
- [x] Preset `termit-browser` в `data/mcp_servers.json` (disabled by default)
- [x] `docs/MCP_BROWSER_RU.md` + skill online-project
- [x] Tests `test_mcp_browser_server.py`; hosted smoke `/api/platform/mcp/servers`

**DoD:** агент может вызывать браузер через `mcp_invoke` + audit; preset документирован.

### Следующий этап (0.4.8): Plan → Build agent enqueue

- [x] `POST /api/orchestration/build-from-plan` — очередь agent run из плана
- [x] `PlanBuildService` + trace span `plan.build_enqueue`
- [x] Desktop Plan panel: Build / Build+Verify → agent run (не только Composer)
- [x] `orchestrationOps.buildFromPlan` в termit-client; Prometheus `plan_build_enqueued_total`

**DoD:** Plan → Build ставит agent run в очередь; метрики и тесты API.

### Следующий этап (0.4.9): A/B onboarding variants + conversion metrics

- [x] Variant A (Quick Start first) vs B (wizard-first) в `FirstRunWizard`
- [x] Telemetry: `onboarding_variant_assigned`, `onboarding_quick_start`, `onboarding_wizard_complete`
- [x] `GET /api/desktop/onboarding-metrics` — conversion по variant
- [x] `onboardingExperiment.ts` + tests; hosted smoke

**DoD:** A/B onboarding измеряется; conversion доступен из API.

### Следующий этап (0.4.10): MCP JSON-RPC full session + onboarding KPI gate

- [x] `McpStdioSession`: ping, resources/list, prompts/list
- [x] Platform API: `/mcp/servers/{id}/ping|resources|prompts`
- [x] KPI gate `onboarding_conversion_min` (≥50%, cohort ≥5)
- [x] Tests `test_mcp_full_jsonrpc.py`

**DoD:** MCP session exposes resources/prompts; onboarding conversion в KPI gates.

### Следующий этап (0.4.11): MCP resources/read + prompts/get + Desktop capabilities

- [x] `McpStdioSession`: `read_resource`, `get_prompt`
- [x] API: `/capabilities`, `POST .../resources/read`, `POST .../prompts/get`
- [x] Desktop MCP list — ping/tools/resources/prompts counts
- [x] Tests extended in `test_mcp_full_jsonrpc.py`

**DoD:** MCP read/get работают через session; Desktop показывает capabilities enabled servers.

### Следующий этап (0.4.12): MCP resource inject + agent read tools + eval P4

- [x] `McpContextService` — catalog + preview resources в agent context
- [x] Tools `mcp_read_resource`, `mcp_get_prompt` (+ auto с `mcp_invoke`)
- [x] Eval P4 `platform_mcp_read`
- [x] Event `mcp_context_injected`

**DoD:** Agent run получает MCP resource context; eval P4 проходит.

### Следующий этап (0.4.13): MCP plan prompt inject + Desktop resource picker + CP21

- [x] `build_plan_prompt_lines` — catalog + preview MCP prompts в plan mode
- [x] Event `mcp_prompt_injected`
- [x] Desktop MCP resource picker (list/read → Composer)
- [x] Eval CP21 `platform_mcp_read` (cursor parity)

**DoD:** Plan mode видит MCP prompts; Desktop читает resources; CP21 проходит.

### Следующий этап (0.4.14): MCP prompt picker + context inject opt-out + P5

- [x] Desktop MCP prompt picker (Composer + Agent plan input)
- [x] `mcp_context_inject` на `AgentRunRequest` + Desktop checkbox
- [x] Eval P5 `platform_mcp_prompt`

**DoD:** Prompt picker работает; inject можно отключить; P5 проходит.

### Следующий этап (0.4.15): MCP telemetry + KPI gates

- [x] `mcp_usage_metrics` из agent run events
- [x] Поля MCP в `/api/ops/agent-runs/metrics`
- [x] `GET /api/desktop/mcp-metrics` + Desktop hint line
- [x] KPI gates `mcp_inject_rate`, `mcp_adoption_rate`

**DoD:** MCP usage виден в ops/desktop; gates в north-star.

### Следующий этап (0.4.16): Web ops dashboard MCP panel

- [x] Dashboard cards: inject rate, tool calls, adoption
- [x] i18n RU/EN + help section
- [x] Tests `test_web_dashboard_mcp.py`

**DoD:** Web UI показывает MCP metrics из agent-runs/metrics.

### Следующий этап (0.4.17): Prometheus MCP + Grafana panel

- [x] `termit_mcp_*` gauges в `/api/metrics/prometheus`
- [x] Grafana SLO dashboard MCP row
- [x] Tests in `test_response_cache_and_metrics.py`

**DoD:** Prometheus/Grafana видят MCP inject и tool usage.

### Следующий этап (0.4.20): Task runner model override

- [x] `TaskCreateRequest.model` + `AgentRunRequest.model` passthrough
- [x] Eval task runner: model → LLM coding path (MT1–MT2)
- [x] SQLite tasks.model column
- [x] Tests `test_task_model_override.py`

**DoD:** Coding task scenarios в benchmark дают разные pass_rate по model.

### Следующий этап (0.4.21): Фаза 5 — оркестратор plan + API plan-status

- [x] `scripts/do_all_plan.sh` — verify_ci → training_loop → DPO probe → live orch → plan status
- [x] `scripts/plan_status_check.py` — CLI + JSON-отчёт blockers/warnings
- [x] `GET /api/ops/plan-status` — тот же отчёт из API (viewer)
- [x] `PlanStatusService` — in-process сбор KPI/GPU/cloud без self-HTTP
- [x] Fix beta cohort: `cohort_size_d30` (не `cohort_size`)
- [x] `do_all_automatic`: opt-in `TERMIT_DO_ALL_PLAN=true`
- [x] smoke extended: `/api/ops/plan-status`

**DoD:** `./scripts/do_all_plan.sh` exit 0; `/api/ops/plan-status` HTTP 200; finetune KPI MB1–MB3 измеряется pre/post train.

**Остаётся (measurement, вне кода):** product KPI gates (beta cohort ≥5), cloud API key, DPO на GPU.

### Следующий этап (0.4.22): Plan status observability + UI

- [x] Prometheus: `termit_plan_status_*`, `termit_plan_finetune_kpi_passed`
- [x] `export_kpi_dashboard.py` — bundle включает `plan_status`
- [x] `data/plan_status_last.json` — автосохранение при GET /api/ops/plan-status
- [x] `scripts/capture_plan_status_snapshot.sh` + monthly crontab
- [x] Web ops: панель plan status + refresh
- [x] Desktop HealthDashboard: строка plan status (RU/EN i18n)
- [x] termit-client: `getPlanStatus` / `planOps.ts`

**DoD:** Prometheus экспортирует plan metrics; KPI export и web/desktop показывают plan status.

### Следующий этап (0.4.23): Learning loop — real train + cloud benchmark

- [ ] GPU runner или облако → real DPO (`TERMIT_DPO_GPU_REQUIRED=true`)
- [ ] `OPENAI_COMPAT_API_KEY` в CI secrets → cloud benchmark green
- [ ] Post-DPO eval на HE1/HE2/MBPP + delta ≥5%
- [x] Grafana SLO dashboard: row plan phase 5
- [x] `.github/workflows/weekly-do-all-plan.yml`

**DoD:** cloud `ready=true`; model-bound eval после real train; weekly CI artifact plan-status.

### Следующий этап (0.4.24): Product KPI из beta telemetry

- [ ] Hosted beta deploy + 5+ пользователей
- [x] `scripts/deploy_hosted_beta.sh` — compose up + hosted_smoke + plan snapshot
- [x] docker-compose: volume `/app/persist` (fix shadowing app code on `/app`)
- [x] Colima/Docker + `deploy_hosted_beta.sh` в do_all (auto-deploy при plan)
- [x] `scripts/seed_beta_cohort_dev.py` — synthetic cohort (TERMIT_BETA_DEV_SEED, dev only)
- [x] BETA_ONBOARDING + HOSTED_DEPLOYMENT: deploy_hosted_beta, plan-status
- [ ] Product gates green на staging с реальной telemetry

**DoD:** cohort_size_d30 ≥5; desktop_kpi_gates overall_passed на beta/staging.

### Следующий этап (0.4.25): Production hardening (Day 90)

- [ ] Push + tagged release
- [ ] TERMIT_PLAN_STATUS_STRICT в release gate (после beta)
- [x] Agent run success gate (`agent_run_success_rate` из `by_outcome_class`)
- [ ] Task success ≥75% на agent runs (не только eval)
- [ ] D30 retention ≥35% на prod beta

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
