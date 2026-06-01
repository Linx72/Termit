#!/usr/bin/env bash
# Local continuous-learning loop without GPU: export datasets, tuning report, optional ollama train.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${TERMIT_STAGE1_ENV_FILE:-${ROOT}/deploy/schedulers/stage1-weekly.env}"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
API_KEY="${TERMIT_API_KEY:-}"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
fi

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="python3"
fi

AUTH=()
if [[ -n "${API_KEY}" ]]; then
  AUTH=(-H "X-API-Key: ${API_KEY}")
fi

echo "[finetune_continuous_learning] bootstrap signals (if empty)..."
"${PYTHON}" "${ROOT}/scripts/finetune_bootstrap_signals.py" || true

echo "[finetune_continuous_learning] export dataset..."
"${PYTHON}" "${ROOT}/scripts/finetune_export.py" --name continuous --min-samples 1 --trajectory || true

echo "[finetune_continuous_learning] DPO export..."
curl -sf "${AUTH[@]}" -X POST "${BASE_URL}/api/finetune/datasets/export-dpo" \
  -H "Content-Type: application/json" \
  -d '{"name":"continuous-dpo","min_pairs":1}' | "${PYTHON}" -m json.tool || true

echo "[finetune_continuous_learning] tuning report..."
curl -sf "${AUTH[@]}" "${BASE_URL}/api/finetune/training/tuning-report" | "${PYTHON}" -m json.tool | head -40

if [[ "${TERMIT_FINETUNE_RUN_STAGE1:-false}" == "true" ]]; then
  echo "[finetune_continuous_learning] stage1 full loop..."
  exec "${ROOT}/scripts/stage1_full_loop.sh"
fi

if [[ "${TERMIT_FINETUNE_TRAINER:-modelfile}" == "ollama" ]]; then
  echo "[finetune_continuous_learning] enqueue stage1 for modelfile/ollama train..."
  "${ROOT}/scripts/stage1_weekly.sh" || true
fi

echo "[finetune_continuous_learning] done."
