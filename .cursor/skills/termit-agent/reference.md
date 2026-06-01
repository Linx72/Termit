# Termit — технический справочник (актуальный)

## Статус фаз (master plan)

| Фаза | Статус | Фокус дальше |
|------|--------|--------------|
| 0 Стабилизация | в основном ✓ | CI e2e, onboarding 10 мин в `START_HERE_RU.md` |
| 1 Agent Platform v2 | ✓ | polish на слабых 7B, spawn sub-run из loop |
| 2 Контекст + platform | ✓ | symbol graph глубже, MCP full JSON-RPC |
| 3 Desktop UX | в работе | Plan mode, terminal, wizard, bilingual polish |
| 4 Eval/finetune loop | частично | eval 2.0, training loop, adapter per repo |
| 5 Production | — | docker, Grafana, DLQ UI |

Документы: [`PROJECT_TASK_PROMPT_RU.md`](../../../PROJECT_TASK_PROMPT_RU.md), [`PLATFORM_PARITY_PLAN_RU.md`](../../../PLATFORM_PARITY_PLAN_RU.md).

**Top 5 спринта (закрыт):** tool loop + verify, SSE в клиентах, semantic retrieval, resume + human confirm, eval gate в CI.

**Следующий фокус:** фаза 3 — onboarding wizard, health dashboard, plan mode, terminal; параллельно фаза 4 — eval 2.0 и training loop.

---

## Карта сервисов (backend)

| Область | Файлы |
|---------|--------|
| Tool loop 2.0 | `agent_loop_service.py`, `tool_json_parser.py`, `loop_step_budget.py`, `tool_loop_metrics.py` |
| Multi-agent | `multi_agent_orchestrator.py`, `orchestration.py` routes |
| Routing | `model_router.py`, `routing_policy_service.py`, `finetune_adapter_resolver.py` |
| Context | `code_retrieval_service.py`, `repo_map_service.py`, `context_packing_service.py`, `context_enrichment_service.py`, `symbol_index_service.py` |
| Platform | `agent_hook_service.py`, `agent_schedule_service.py`, `mcp_registry_service.py`, `skill_store.py`, `guardrail_service.py`, `trace_span_store.py`, `search_provider.py` |
| Projects | `project_rules_store.py`, `agent_templates_store.py` |
| Runs | `sqlite_agent_run_store.py`, `agent_run_notifier.py`, `agent_run_store.py` |
| Finetune | `finetune_service.py`, `finetune_trainer_service.py`, `finetune_dataset_curator.py`, `finetune_trajectory_export.py`, `finetune_gguf_converter.py` |
| Eval / gate | `eval_service.py`, `eval_ci_gate.py`, `agent_eval_service.py` |
| Verify | `verify_command_resolver.py` |

Wiring: `app/state.py`, `app/core/config.py`, `app/domain/schemas.py`, `app/main.py`.

---

## API surface

### Core

- Chat: `POST /api/chat`, `POST /api/chat/stream`
- Local: `/api/local/status`, `/api/local/models`, pull
- Routing: `/api/routing/*`
- Retrieval: `/api/retrieval/*`, symbols `/api/retrieval/symbols/*`
- Eval: `/api/eval/*`, agent eval `/api/agents/eval/*`
- Finetune: `/api/finetune/*`
- Ops: `/healthz`, `/api/metrics/*`, `/api/ops/readiness`, agent-runs metrics

### Agents

- Profiles: `GET/POST /api/agents`, `GET /api/agents/{id}`
- Runs: `POST /api/agents/{id}/runs`, `GET /api/agents/runs/{run_id}`
- Timeline: `GET .../events`, `GET .../stream` (SSE)
- Control: `POST .../cancel`, `.../confirm`, `.../resume`, DLQ replay
- Tools (RBAC): `POST /api/agents/{id}/tools/{list_files,read_file,execute_command,apply_patch,web_automation}`
- Memory: `GET /api/agents/{id}/memory`

### Projects & orchestration

- `GET/POST /api/projects/{root}/rules`
- Agent templates: `/api/projects/.../templates`
- `POST /api/orchestration/plan` (multi-agent)

### Platform (`/api/platform`)

- Skills: `GET /skills`, `GET /skills/{id}`
- Hooks: `GET /hooks/status`
- Guardrails: `POST /guardrails/check`
- Traces: `GET /runs/{run_id}/spans`
- MCP: list/upsert servers, `POST /mcp/invoke`
- Schedules: cron agent runs
- Search: Perplexity/stub status

---

## Clients

| Пакет | Экспорт / паттерн |
|-------|-------------------|
| `termit-client` | `TermitClient`, `TermitAgent`, `TermitRun`, `TermitAgent.resume`, `platform.ts` |
| Desktop | SSE timeline, PlanPanel, HealthDashboard, ModelManager, TerminalPanel, i18n |
| VS Code | Agents tab SSE-first, SDK consumer |

UX-спека: `clients/CLIENT_UX.md`.

---

## Данные и конфиг

- Agents: `data/agents.json`, templates `data/agent_templates.json`
- Runs: SQLite (путь из config)
- Finetune: `data/finetune/training_signals.jsonl`, `data/finetune/datasets/*.jsonl`
- Eval: `data/eval_scenarios.json`, `data/eval_reports.jsonl`
- Skills (product): `data/skills/` (формат как `.cursor/skills/`)
- Hooks: `data/hooks/`, preset из `.cursor/hooks/token_watch.py`

---

## Проверки

```bash
cd /Users/orosam/Projects/Termit
source .venv/bin/activate
python -m unittest discover -s tests -q
# точечно:
python -m unittest tests.test_platform_parity tests.test_phase1 tests.test_phase2 -q
```

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8765
./scripts/smoke_http.sh
python scripts/eval_ci_gate.py   # при изменениях eval gate
```

Auth: `X-API-Key` из `.env` (`dev-key`, `viewer-key`).

---

## Rules (always apply)

- `.cursor/rules/termit-agent-identity.mdc`
- `.cursor/rules/respond-in-russian.mdc`
- `.cursor/rules/verify-after-serious-changes.mdc`

## Архив skill

Снимок milestones до platform v2: [archive/reference-sessions-baseline.md](archive/reference-sessions-baseline.md).
