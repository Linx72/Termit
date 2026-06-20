#!/usr/bin/env bash
# DPO export + HF DPO train when GPU is available; dry-run fallback otherwise.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate" 2>/dev/null || true

NAME="${TERMIT_DPO_TRAIN_NAME:-weekly-dpo-gpu}"
GPU_JSON="$("${PYTHON_BIN}" "${ROOT}/scripts/gpu_probe.py")"
GPU_OK="$(echo "${GPU_JSON}" | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin).get('gpu_available', False))")"

echo "GPU probe: ${GPU_JSON}"

if [[ "${GPU_OK}" == "True" || "${GPU_OK}" == "true" ]]; then
  export TERMIT_FINETUNE_HF_DRY_RUN=false
  export TERMIT_FINETUNE_AUTO_TRAIN_DPO=true
  echo "GPU detected — running real HF DPO train (TERMIT_FINETUNE_HF_DRY_RUN=false)"
else
  if [[ "${TERMIT_DPO_GPU_REQUIRED:-false}" == "true" ]]; then
    echo "TERMIT_DPO_GPU_REQUIRED=true but no GPU found." >&2
    exit 1
  fi
  export TERMIT_FINETUNE_HF_DRY_RUN=true
  export TERMIT_FINETUNE_AUTO_TRAIN_DPO=true
  echo "No GPU — dry-run train only (set TERMIT_DPO_GPU_REQUIRED=true to fail hard)"
fi

RESULT_JSON="${TERMIT_DPO_TRAIN_RESULT_JSON:-/tmp/termit_dpo_train_result.json}"

exec "${PYTHON_BIN}" "${ROOT}/scripts/finetune_dpo_pipeline.py" \
  --name "${NAME}" \
  --min-pairs "${TERMIT_DPO_MIN_PAIRS:-1}" \
  --train \
  --train-result "${RESULT_JSON}"
