#!/usr/bin/env bash
# CI-safe learning loop 0.4.23: offline HE/MBPP + DPO dry-run + cloud probe (без MB1–MB3 LLM).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export TERMIT_EVAL_POST_DPO_IDS="${TERMIT_EVAL_POST_DPO_IDS:-HE1,HE2,MBPP1,MBPP2}"
export TERMIT_LEARNING_LOOP_SKIP_MODEL_BENCHMARK="${TERMIT_LEARNING_LOOP_SKIP_MODEL_BENCHMARK:-true}"
export TERMIT_FINETUNE_KPI_STRICT="${TERMIT_FINETUNE_KPI_STRICT:-false}"
export TERMIT_DPO_GPU_REQUIRED="${TERMIT_DPO_GPU_REQUIRED:-false}"

exec "${ROOT}/scripts/learning_loop_0423.sh"
