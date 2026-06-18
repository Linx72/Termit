#!/usr/bin/env bash
# Capture eval pass_rate baseline for finetune KPI gate (TERMIT_FINETUNE_MIN_EVAL_IMPROVEMENT).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
API_KEY="${TERMIT_API_KEY:-}"
OUTPUT="${TERMIT_EVAL_KPI_BASELINE:-${ROOT}/data/eval_kpi_baseline.json}"
CATEGORY="${TERMIT_EVAL_CATEGORY:-cursor_parity}"
LIMIT="${TERMIT_EVAL_LIMIT:-20}"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate" 2>/dev/null || true

curl_api() {
  if [[ -n "${API_KEY}" ]]; then
    curl -sf -H "X-API-Key: ${API_KEY}" "$@"
  else
    curl -sf "$@"
  fi
}

echo "== Capture eval KPI baseline (category=${CATEGORY}, limit=${LIMIT}) =="

if ! curl_api --max-time 5 "${BASE_URL}/health" >/dev/null 2>&1; then
  echo "Termit API not reachable at ${BASE_URL}" >&2
  exit 1
fi

mkdir -p "$(dirname "${OUTPUT}")"
curl_api -X POST "${BASE_URL}/api/eval/run-suite" \
  -H "Content-Type: application/json" \
  -d "{\"category\":\"${CATEGORY}\",\"limit\":${LIMIT},\"persist_report\":true}" \
  | tee "${OUTPUT}" \
  | "${PYTHON_BIN}" -m json.tool | head -20

PASS_RATE="$("${PYTHON_BIN}" -c "import json,sys; print(json.load(open(sys.argv[1]))['pass_rate'])" "${OUTPUT}")"
echo "OK — baseline saved to ${OUTPUT} (pass_rate=${PASS_RATE})"
