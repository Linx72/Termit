#!/usr/bin/env bash
# Export DPO pairs (bootstrap if needed) and validate dataset contract.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate" 2>/dev/null || true

NAME="${TERMIT_DPO_EXPORT_NAME:-do-all-verify-dpo}"
MIN_PAIRS="${TERMIT_DPO_MIN_PAIRS:-1}"
MIN_ROWS="${TERMIT_DPO_CONTRACT_MIN_ROWS:-1}"

echo "== DPO export + contract gate (name=${NAME}) =="

EXPORT_RAW="$(
  TERMIT_DPO_REQUIRED="${TERMIT_DPO_REQUIRED:-false}" \
    "${PYTHON_BIN}" "${ROOT}/scripts/finetune_dpo_pipeline.py" \
      --name "${NAME}" \
      --min-pairs "${MIN_PAIRS}"
)"
EXPORT_JSON="$(
  printf '%s' "${EXPORT_RAW}" | "${PYTHON_BIN}" -c "
import json, sys
text = sys.stdin.read().strip()
start = text.find('{')
if start < 0:
    sys.exit(1)
obj, _end = json.JSONDecoder().raw_decode(text, start)
print(json.dumps(obj))
"
)"

DATASET_PATH="$(
  echo "${EXPORT_JSON}" | "${PYTHON_BIN}" -c "
import json, sys
payload = json.load(sys.stdin)
if payload.get('skipped'):
    print('')
else:
    print(str(payload.get('dataset_path', '')).strip())
"
)"

if [[ -z "${DATASET_PATH}" ]]; then
  FALLBACK="${ROOT}/data/finetune/datasets/sample_dpo_contract.jsonl"
  if [[ -f "${FALLBACK}" ]]; then
    echo "DPO export skipped — fallback to ${FALLBACK}" >&2
    DATASET_PATH="${FALLBACK}"
  else
    echo "DPO export did not return dataset_path." >&2
    echo "${EXPORT_RAW}" >&2
    exit 1
  fi
fi

"${PYTHON_BIN}" "${ROOT}/scripts/eval_dpo_contract_gate.py" \
  --dataset "${DATASET_PATH}" \
  --min-rows "${MIN_ROWS}"

echo "OK — DPO contract gate passed (${DATASET_PATH}, pairs=$(echo "${EXPORT_JSON}" | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin).get('pair_count',0))"))"
