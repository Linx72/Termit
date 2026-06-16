# Finetune loop (Termit)

Замкнутый цикл: **agent runs → signals → dataset → train → eval → regression gate → promote/shadow**.

## Скрипты

| Скрипт | Назначение |
|--------|------------|
| [`scripts/finetune_continuous_learning.sh`](file:///Users/amoros/Projects/Termit/scripts/finetune_continuous_learning.sh) | Ежедневный export + DPO + tuning report |
| [`scripts/training_loop_week2.sh`](file:///Users/amoros/Projects/Termit/scripts/training_loop_week2.sh) | Signals → dataset → finetune job |
| [`scripts/training_loop_full.sh`](file:///Users/amoros/Projects/Termit/scripts/training_loop_full.sh) | Week2 + eval suite + regression vs baseline |
| [`scripts/stage1_full_loop.sh`](file:///Users/amoros/Projects/Termit/scripts/stage1_full_loop.sh) | Stage1 train + post-eval + promote |
| [`scripts/eval_regression_report.py`](file:///Users/amoros/Projects/Termit/scripts/eval_regression_report.py) | Gate: pass-rate delta vs baseline |

## Быстрый прогон (локально)

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8765 &
./scripts/training_loop_full.sh
```

Переменные:

| Env | Default | Смысл |
|-----|---------|--------|
| `TERMIT_BASE_URL` | `http://127.0.0.1:8765` | API |
| `TERMIT_EVAL_BASELINE` | `data/eval_baseline_release.json` | Baseline report |
| `TERMIT_EVAL_CATEGORY` | `cursor_parity` | Eval category |
| `TERMIT_EVAL_LIMIT` | `20` | Scenarios |
| `TERMIT_EVAL_MAX_PASS_RATE_DROP` | `0.05` | Max regression |

## Promote / shadow

Backend: `FinetuneService._finalize_training_deploy` + `evaluate_training_regression`.

Флаги `.env`:

- `TERMIT_FINETUNE_REGRESSION_GATE_ENABLED=true`
- `TERMIT_FINETUNE_REGRESSION_REQUIRE_POST_EVAL=true`
- `TERMIT_FINETUNE_SHADOW_TRAFFIC_PERCENT=10`

## CI

- **PR/main:** fast eval gate (cursor_parity 20)
- **Nightly:** deep eval 53 + `eval_regression_report.py` vs baseline
- **Release (local):** `TERMIT_EVAL_GATE_TIER=release ./scripts/release_smoke_extended.sh`

## KPI цель (parity plan)

+5% eval pass после одного finetune cycle — измеряется сравнением `pass_rate` до/после stage1; зафиксируй baseline через `persist_report` и обнови `data/eval_baseline_release.json` после стабильного релиза.
