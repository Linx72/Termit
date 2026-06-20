#!/usr/bin/env bash
# CI-safe learning loop 0.4.23: tool fixtures (HE/MBPP/SWE/TB) + DPO dry-run + cloud probe.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export TERMIT_LEARNING_LOOP_SKIP_MODEL_BENCHMARK="${TERMIT_LEARNING_LOOP_SKIP_MODEL_BENCHMARK:-true}"
export TERMIT_FINETUNE_KPI_STRICT="${TERMIT_FINETUNE_KPI_STRICT:-false}"
export TERMIT_DPO_GPU_REQUIRED="${TERMIT_DPO_GPU_REQUIRED:-false}"
export TERMIT_RUN_CLOUD_BENCHMARK="${TERMIT_RUN_CLOUD_BENCHMARK:-false}"
# POST_DPO_IDS не задаём — eval_standalone подставит HE/MBPP/SWE/TB без MB/MT.

exec "${ROOT}/scripts/learning_loop_0423.sh"
