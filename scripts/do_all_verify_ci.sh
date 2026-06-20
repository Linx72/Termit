#!/usr/bin/env bash
# CI-friendly do-all verify (server already running with orchestration env).
set -euo pipefail

export TERMIT_DO_ALL_CI=true
export TERMIT_ORCH_SKIP_SERVER_RESTART=true
export TERMIT_ORCH_SPIKE_USE_FIXTURE=true
export TERMIT_ORCH_ENABLE_EVAL_FIXTURE=true
export TERMIT_RUN_CLOUD_BENCHMARK=false
export TERMIT_CAP_GATE_TIER="${TERMIT_CAP_GATE_TIER:-ci}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# На CI нет training signals — используем seed DPO contract вместо export.
export TERMIT_DPO_DATASET="${TERMIT_DPO_DATASET:-${ROOT}/data/finetune/datasets/sample_dpo_contract.jsonl}"
exec "${ROOT}/scripts/do_all_verify.sh"
