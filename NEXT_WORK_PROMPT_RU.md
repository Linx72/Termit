# Termit — промпт на дальнейшие работы

> **Назначение:** handoff для следующих сессий агента. При «do all», «что дальше», «продолжай Phase 4» — **начинать отсюда**, затем сверяться с `PROJECT_TASK_PROMPT_RU.md`.
>
> **Обновлено:** 2026-06-01 (после 4 итераций training loop).

**Северная звезда:** Termit.app → репо → задача → агент читает код, правит, гоняет тесты, отчитывается — без ручного копирования в чат.

---

## Что уже сделано (не трогать без причины)

### Agent Platform v2 (фазы 0–2 — закрыты)
- Tool loop 2.0: native tools + JSON fallback, verify-after-patch, resume, human confirm
- Multi-agent orchestrator, routing policy, repo profiles, dual-pass
- Retrieval hybrid, symbol index, repo map, context packing
- Platform API: MCP, skills, hooks, guardrails, schedules, traces
- Desktop UX: SSE timeline, wizard, plan mode, terminal, health dashboard

### Finetune / training loop (фаза 4 — pipeline готов, данные/GPU — нет)
| Компонент | Статус | Ключевые файлы |
|-----------|--------|----------------|
| Training signals (tool steps, negatives, patch revert) | ✓ | `training_signal_store.py`, `patch_outcome_store.py` |
| Trajectory SFT export из agent runs | ✓ | `finetune_trajectory_export.py`, `POST .../export-trajectory-sft` |
| DPO pairs (`chosen` + `rejected`) | ✓ | `finetune_dpo_export.py`, `POST .../export-dpo` |
| Dataset curator + stratified export | ✓ | `finetune_dataset_curator.py`, `scripts/finetune_export.py` |
| Trainer: modelfile / ollama / hf (Unsloth dry-run) | ✓ | `finetune_trainer_service.py`, `scripts/unsloth_qlora_train.py` |
| GGUF converter + ADAPTER в Modelfile | ✓ | `finetune_gguf_converter.py` |
| Adapter resolver + routing fallback | ✓ | `finetune_adapter_resolver.py`, `routing_policy_service.py` |
| Stage1 pipeline + regression gate | ✓ | `finetune_service.py`, `finetune_regression_gate.py` |
| Tool loop tuning report | ✓ | `tool_loop_tuning_service.py`, `GET .../training/tuning-report` |
| Agent runs → repo_profile routing | ✓ | `repo_profile_resolver.py`, `AgentRunRequest.repo_profile` |
| Local continuous learning script | ✓ | `scripts/finetune_continuous_learning.sh`, `finetune_bootstrap_signals.py` |
| CI: finetune e2e + eval gate | ✓ | `.github/workflows/ci.yml` |

---

## Главный gap (почему exit criteria Phase 4 не закрыт)

**Exit criteria Phase 4:** measurable **+5–10% eval pass rate** после одного цикла finetune + gate блокирует регрессии.

| Блокер | Симптом | Что нужно |
|--------|---------|-----------|
| Нет DPO negatives в prod | `export-dpo` → 400, `dpo_negative_count=0` | Накопить failed tool steps / patch reverts через реальные agent runs |
| Trajectory SFT пустой | `export-trajectory-sft` → 400 без runs | ≥50 agent runs с `tool_loop_trace` events |
| HF train = dry-run | Веса не меняются | GPU + `TERMIT_FINETUNE_HF_DRY_RUN=false` + `pip install unsloth` |
| GGUF без llama.cpp | ADAPTER не в Ollama | `TERMIT_FINETUNE_LLAMA_CPP_PATH` + `HF_AUTO_GGUF=true` |
| Старый uvicorn | Новые endpoints 404 на `:8765` | `./scripts/restart_server.sh` после deploy |

**Вывод:** код pipeline **готов**; следующий спринт — **данные + один реальный train cycle + измеримый eval delta**.

---

## Top 5 — ближайший спринт (2 недели)

### 1. Накопить training data (P0)
**Цель:** ≥50 trajectory runs + ≥20 DPO pairs с matching `chosen`.

- [ ] Прогнать eval suite с `use_tool_loop=true` и persist runs (`agent_eval_service`)
- [ ] Включить capture: `TERMIT_FINETUNE_AUTO_CAPTURE_SIGNALS=true`, `TERMIT_FINETUNE_CAPTURE_PATCH_REVERTS=true`
- [ ] Smoke: `POST /api/finetune/datasets/export-dpo` → **200**, `pair_count ≥ 1`
- [ ] Smoke: `POST /api/finetune/datasets/export-trajectory-sft` → **200**, `sample_count ≥ 10`

**Файлы:** `app/services/agent_eval_service.py`, `data/eval_scenarios.json`, `scripts/finetune_bootstrap_signals.py` (только dev fallback)

### 2. Один полный train cycle на GPU или ollama (P0)
**Цель:** adapter зарегистрирован, `GET /api/finetune/adapters/resolve?repo_profile_id=termit-core` → новая модель.

```bash
# Локально без GPU (modelfile/ollama):
TERMIT_FINETUNE_TRAINER=ollama TERMIT_FINETUNE_RUN_STAGE1=true \
  ./scripts/finetune_continuous_learning.sh

# С GPU (Unsloth QLoRA):
pip install unsloth
export TERMIT_FINETUNE_TRAINER=hf
export TERMIT_FINETUNE_HF_DRY_RUN=false
export TERMIT_FINETUNE_HF_AUTO_GGUF=true
export TERMIT_FINETUNE_LLAMA_CPP_PATH=/path/to/llama.cpp
./scripts/stage1_full_loop.sh
```

- [ ] Post-eval baseline vs trained delta зафиксирован в `data/eval_reports.jsonl`
- [ ] Regression gate: promote или shadow, не silent fail

**Файлы:** `finetune_trainer_service.py`, `scripts/stage1_full_loop.sh`, `scripts/post_stage1_train.py`

### 3. Измерить +5–10% eval и зафиксировать в CI (P0)
**Цель:** доказуемый прирост pass rate; gate в release smoke.

- [ ] Baseline eval run → JSON report (pass_rate, total)
- [ ] Post-finetune eval run → сравнение
- [ ] Скрипт `scripts/finetune_eval_delta.sh`: baseline → train → post-eval → delta report
- [ ] Порог в CI: не блокировать на отсутствии GPU, но **блокировать регрессию** если delta < 0

**Файлы:** `app/services/eval_ci_gate.py`, `scripts/eval_ci_gate.py`, `scripts/release_smoke.sh`

### 4. DPO train path (P1)
**Цель:** не только SFT/modelfile — preference tuning на `chosen/rejected`.

- [ ] Экспорт DPO JSONL уже есть; добавить TRL DPO runner (`scripts/dpo_train.py` или расширить `unsloth_qlora_train.py`)
- [ ] `FinetuneTrainRequest` / stage1: `training_mode=sft|dpo|both`
- [ ] Unit test: mock trainer принимает DPO format

**Файлы:** `finetune_trainer_service.py`, `finetune_service.py`, `scripts/unsloth_qlora_train.py`

### 5. Agent run → auto repo_profile в клиентах (P1)
**Цель:** finetune adapter подхватывается без ручного `repo_profile`.

- [ ] Desktop / VS Code: передавать `workspace_scope` + infer `repo_profile` из открытого workspace
- [ ] UI: показывать resolved model в agent run timeline (`attempted_models[0]`)
- [ ] E2E: agent run с `retrieval_path_prefix=app/` → model = adapter для `termit-core`

**Файлы:** `clients/termit-client/src/agent.ts`, `clients/vscode-extension/`, `clients/termit-desktop/`

---

## Фаза 4 — оставшийся backlog (после Top 5)

### 4.4 Data quality
- [ ] Git revert detection (сейчас только file hash watch в `patch_outcome_store`)
- [ ] Curator: down-rank trajectories рядом с patch_revert (heuristic по `run_id` / path)
- [ ] Min quality score для positives в DPO pairing

### 4.5 Observability training loop
- [ ] Prometheus metrics: `finetune_export_samples`, `dpo_pairs`, `train_job_duration`
- [ ] Dashboard widget: last train delta, adapter version, shadow traffic %
- [ ] Alert: `dpo_negative_count` spike → tuning report auto-link

### 4.6 E2E test chain
- [ ] `tests/test_finetune_full_pipeline_e2e.py`: bootstrap → export → stage1 (mock trainer) → register adapter → resolve
- [ ] Не требовать GPU в CI; mock `FinetuneTrainerService.run_hf`

---

## Фаза 5 — старт после закрытия Phase 4 exit criteria

Приоритет по `PROJECT_TASK_PROMPT_RU.md`:

1. Docker compose prod + backup SQLite
2. Grafana из Prometheus + alert на failed runs spike
3. UI API keys / team quotas
4. Graceful shutdown workers + dead-letter queue UI
5. Secret scan in patches + sandbox hardening

---

## Инструкция для агента

### При «do all»
1. Взять **Top 5 целиком** или один блок P0 — не распыляться
2. Минимальный diff, паттерны `finetune_*`, `agent_*`, `scripts/*`
3. **Проверять сам:** unittest + smoke `:8765` (перезапустить сервер если 404 на новых endpoints)
4. Итог: **passed/failed**, HTTP-коды, числа (pair_count, pass_rate delta)
5. Ответы — **русский**

### Smoke (finetune)

```bash
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/api/finetune/adapters/resolve?repo_profile_id=termit-core | head
curl -s http://127.0.0.1:8765/api/finetune/training/tuning-report | head
curl -s -X POST http://127.0.0.1:8765/api/finetune/datasets/export-dpo \
  -H 'Content-Type: application/json' -d '{"name":"check","min_pairs":1}'
curl -s -X POST http://127.0.0.1:8765/api/finetune/datasets/export-trajectory-sft \
  -H 'Content-Type: application/json' -d '{"name":"check","min_samples":1,"min_messages":3}'
```

### Unit tests (finetune scope)

```bash
python3 -m unittest discover -s tests -p 'test_finetune*.py' -q
python3 -m unittest tests.test_finetune_dpo_export tests.test_finetune_pipeline_e2e \
  tests.test_training_signal_store tests.test_repo_profile_resolver -v
```

### Env (ключевые)

```env
TERMIT_FINETUNE_TRAINER=ollama|hf|modelfile|off
TERMIT_FINETUNE_HF_DRY_RUN=true
TERMIT_FINETUNE_HF_AUTO_GGUF=true
TERMIT_FINETUNE_HF_AUTO_OLLAMA=false
TERMIT_FINETUNE_LLAMA_CPP_PATH=
TERMIT_FINETUNE_ADAPTERS_DIR=./data/finetune/adapters
TERMIT_FINETUNE_CAPTURE_PATCH_REVERTS=true
TERMIT_FINETUNE_REPO_PROFILE_ID=termit-core
TERMIT_EVAL_MIN_PASS_RATE=0.95
```

---

## Definition of Done — закрытие Phase 4

- [ ] `export-dpo` и `export-trajectory-sft` стабильно **200** на prod data (не bootstrap)
- [ ] Один полный cycle: export → train → GGUF/ollama → register → promote/shadow
- [ ] Post-eval pass_rate **≥ baseline + 5%** (или documented reason why not on this hardware)
- [ ] Regression gate блокирует promote при delta < 0
- [ ] Agent run с workspace автоматически использует adapter model
- [ ] CI green: unittest + finetune e2e + eval gate

---

## Риски

| Риск | Митигация |
|------|-----------|
| Finetune без negatives | Сначала agent eval runs с intentional failures; не полагаться на bootstrap |
| GPU недоступен в CI | CI = mock trainer; реальный train — локальный `stage1_full_loop.sh` |
| Modelfile ≠ real weights | Документировать: ollama path = prompt tuning; hf path = LoRA weights |
| Scope creep Phase 5 | Не начинать Docker/Grafana пока Phase 4 DoD не закрыт |

---

## Связанные документы

| Документ | Назначение |
|----------|------------|
| `PROJECT_TASK_PROMPT_RU.md` | Master plan фазы 0–5 |
| `PLATFORM_PARITY_PLAN_RU.md` | Cursor/OpenAI parity sprints |
| `.cursor/skills/termit-agent/SKILL.md` | Identity + workflows агента |
| `START_HERE_RU.md` | Onboarding пользователя |
