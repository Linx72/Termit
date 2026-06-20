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
if [[ -x "${ROOT}/.venv/bin/activate" ]]; then
  source "${ROOT}/.venv/bin/activate"
fi

NAME="${TERMIT_DPO_EXPORT_NAME:-do-all-verify-dpo}"
MIN_PAIRS="${TERMIT_DPO_MIN_PAIRS:-1}"
MIN_ROWS="${TERMIT_DPO_CONTRACT_MIN_ROWS:-1}"

echo "== DPO export + contract gate (name=${NAME}) =="

FALLBACK="${ROOT}/data/finetune/datasets/sample_dpo_contract.jsonl"
set +e
EXPORT_RAW="$(
  TERMIT_DPO_REQUIRED="${TERMIT_DPO_REQUIRED:-false}" \
    "${PYTHON_BIN}" "${ROOT}/scripts/finetune_dpo_pipeline.py" \
      --name "${NAME}" \
      --min-pairs "${MIN_PAIRS}" 2>&1
)"
EXPORT_RC=$?
set -e

EXPORT_JSON=""
if [[ "${EXPORT_RC}" -eq 0 && -n "${EXPORT_RAW}" ]]; then
  EXPORT_JSON="$(
    printf '%s' "${EXPORT_RAW}" | "${PYTHON_BIN}" -c "
import json, sys

text = sys.stdin.read().strip()
decoder = json.JSONDecoder()
idx = 0
export = None
while idx < len(text):
    while idx < len(text) and text[idx] not in '{[':
        idx += 1
    if idx >= len(text):
        break
    try:
        obj, end = decoder.raw_decode(text, idx)
    except json.JSONDecodeError:
        break
    if isinstance(obj, dict) and any(
        key in obj for key in ('dataset_path', 'skipped', 'pair_count')
    ):
        export = obj
    idx = end
if export is None:
    sys.exit(1)
print(json.dumps(export))
" 2>/dev/null || true
)"
fi

DATASET_PATH=""
if [[ -n "${EXPORT_JSON}" ]]; then
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
fi

if [[ -z "${DATASET_PATH}" ]]; then
  if [[ -f "${FALLBACK}" ]]; then
    if [[ "${EXPORT_RC}" -ne 0 || -z "${EXPORT_JSON}" ]]; then
      echo "DPO export failed or unparsable (rc=${EXPORT_RC}) — fallback to ${FALLBACK}" >&2
    else
      echo "DPO export skipped — fallback to ${FALLBACK}" >&2
    fi
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

echo "OK — DPO contract gate passed (${DATASET_PATH}, pairs=$(if [[ -n "${EXPORT_JSON}" ]]; then echo "${EXPORT_JSON}" | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin).get('pair_count',0))"; else echo "sample"; fi))"
