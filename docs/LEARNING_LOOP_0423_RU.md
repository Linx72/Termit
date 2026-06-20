# Learning loop 0.4.23 — real DPO + post-eval + cloud benchmark

Этап закрывает **real train path**, **post-DPO eval** (MB1–MB3 + HE1/HE2 + MBPP) и **cloud benchmark** для фазы 5.

## Быстрый старт (локально, dry-run DPO)

```bash
./scripts/learning_loop_0423.sh
```

Без NVIDIA GPU скрипт выполнит DPO dry-run, pre/post eval и запишет артефакт `data/learning_loop_0423_last.json`.

## Real GPU DPO (локально)

```bash
export TERMIT_DPO_GPU_REQUIRED=true
export TERMIT_FINETUNE_HF_DRY_RUN=false
# pip install unsloth trl datasets transformers  # на машине с CUDA
./scripts/learning_loop_0423.sh
```

## Remote GPU (RunPod / Vast / свой сервер)

```bash
export TERMIT_REMOTE_GPU_SSH=user@gpu-host.example
export TERMIT_REMOTE_GPU_DIR=/tmp/termit-dpo
export TERMIT_DPO_GPU_REQUIRED=true
./scripts/learning_loop_0423.sh
```

`gpu_probe.py` при `TERMIT_REMOTE_GPU_SSH` проверяет GPU на удалённом хосте.

## Cloud benchmark

```bash
export OPENAI_COMPAT_API_KEY=sk-...
export TERMIT_CLOUD_BENCHMARK_REQUIRED=true   # fail hard если probe not ready
./scripts/learning_loop_0423.sh
```

Dev stub (только local): `TERMIT_CLOUD_BENCHMARK_DEV_READY=true`.

## Post-DPO сценарии

По умолчанию (`TERMIT_EVAL_POST_DPO_FULL=true`):

| ID | Набор |
|----|-------|
| MB1–MB3 | model benchmark KPI |
| HE1, HE2 | HumanEval fixtures |
| MBPP1, MBPP2 | MBPP fixtures |

Override: `TERMIT_EVAL_POST_DPO_IDS=MB1,HE1`.

## KPI gate

Цель: **+5%** pass rate post-DPO vs pre-DPO baseline.

- Baseline: `data/eval_kpi_baseline_dpo.json`
- Post-DPO: `data/eval_post_dpo_last.json`
- KPI summary: `data/eval_kpi_last.json`
- Strict: `TERMIT_FINETUNE_KPI_STRICT=true`

## CI (offline tools + dry-run DPO)

```bash
./scripts/learning_loop_0423_ci.sh
```

HE/MBPP без LLM — для weekly macOS CI. KPI +5% **не измерим** без real DPO + MB1–MB3.

## GPU workflow (GitHub Actions)

`.github/workflows/gpu-dpo-learning-loop.yml` — `workflow_dispatch` на self-hosted runner `[self-hosted, gpu, nvidia]`.

## Интеграция в do_all_plan

```bash
TERMIT_DO_ALL_LEARNING_0423=true ./scripts/do_all_plan.sh
```

## Plan status

`plan_status_check.py` / `GET /api/ops/plan-status` читают:

- `data/eval_kpi_last.json` — finetune KPI
- `data/learning_loop_0423_last.json` — `dpo_real_train`, cloud run
- warnings: `dpo_dry_run`, `finetune_kpi_dev_seed`, `cloud_benchmark`, `no_gpu`

## CI (weekly)

`.github/workflows/weekly-do-all-plan.yml` — при `OPENAI_COMPAT_API_KEY` в secrets включает cloud benchmark через `TERMIT_DO_ALL_TRY_CLOUD`.

Артефакты: `plan-status` (+ `learning_loop_0423_last.json` при полном цикле).
