#!/usr/bin/env bash
# Удалённый DPO train через SSH (RunPod/Vast/свой GPU-сервер).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE="${TERMIT_REMOTE_GPU_SSH:?TERMIT_REMOTE_GPU_SSH required (user@host)}"
REMOTE_DIR="${TERMIT_REMOTE_GPU_DIR:-/tmp/termit-dpo}"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

echo "== Remote GPU DPO via SSH (${REMOTE}:${REMOTE_DIR}) =="

ssh "${REMOTE}" "mkdir -p '${REMOTE_DIR}/scripts' '${REMOTE_DIR}/data/finetune' '${REMOTE_DIR}/app/services'"

RSYNC_EXCLUDES=(
  --exclude '.git'
  --exclude '.venv'
  --exclude 'node_modules'
  --exclude 'data/adapters'
  --exclude 'data/eval_reports'
)
rsync -az "${RSYNC_EXCLUDES[@]}" \
  "${ROOT}/scripts/dpo_gpu_train.sh" \
  "${ROOT}/scripts/finetune_dpo_pipeline.py" \
  "${ROOT}/scripts/gpu_probe.py" \
  "${ROOT}/scripts/unsloth_dpo_train.py" \
  "${ROOT}/scripts/eval_dpo_contract_gate.py" \
  "${REMOTE}:${REMOTE_DIR}/scripts/"

rsync -az "${RSYNC_EXCLUDES[@]}" \
  "${ROOT}/app/" \
  "${REMOTE}:${REMOTE_DIR}/app/"

rsync -az "${RSYNC_EXCLUDES[@]}" \
  "${ROOT}/data/finetune/" \
  "${REMOTE}:${REMOTE_DIR}/data/finetune/" 2>/dev/null || true

rsync -az "${ROOT}/requirements.txt" "${REMOTE}:${REMOTE_DIR}/requirements.txt"

ssh "${REMOTE}" bash -s <<EOF
set -euo pipefail
cd '${REMOTE_DIR}'
export TERMIT_DPO_GPU_REQUIRED=true
export TERMIT_FINETUNE_HF_DRY_RUN=false
export TERMIT_FINETUNE_AUTO_TRAIN_DPO=true
export TERMIT_PROJECT_ROOT='${REMOTE_DIR}'
export PYTHONPATH='${REMOTE_DIR}'

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt || pip install -q fastapi pydantic httpx

GPU_JSON="\$(python3 scripts/gpu_probe.py)"
echo "Remote GPU probe: \${GPU_JSON}"
GPU_OK="\$(echo "\${GPU_JSON}" | python3 -c "import json,sys; print(json.load(sys.stdin).get('gpu_available', False))")"
if [[ "\${GPU_OK}" != "True" && "\${GPU_OK}" != "true" ]]; then
  echo "Remote host has no GPU." >&2
  exit 1
fi

bash scripts/dpo_gpu_train.sh
EOF

echo ""
echo "== Sync adapters back =="
rsync -az "${REMOTE}:${REMOTE_DIR}/data/adapters/" "${ROOT}/data/adapters/" 2>/dev/null || true

"${PYTHON_BIN}" "${ROOT}/scripts/gpu_probe.py"
