#!/usr/bin/env bash
# Refresh eval capability baseline from recent benchmark history (manual or post-cloud-run).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
API_KEY="${TERMIT_API_KEY:-}"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
LIMIT="${TERMIT_CAP_REVIEW_LIMIT:-12}"
BASELINE_PATH="${TERMIT_EVAL_CAPABILITY_BASELINE_PATH:-${ROOT}/data/eval_capability_baseline.json}"

curl_auth() {
  if [[ -n "${API_KEY}" ]]; then
    curl -sf -H "X-API-Key: ${API_KEY}" "$@"
  else
    curl -sf "$@"
  fi
}

echo "== Capability baseline refresh (limit=${LIMIT}) =="
echo "Target: ${BASELINE_PATH}"

if curl_auth --max-time 5 "${BASE_URL}/health" >/dev/null 2>&1; then
  echo "Using API POST /api/eval/benchmark/capability-baseline/refresh"
  ENCODED_PATH="$("${PYTHON_BIN}" -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "${BASELINE_PATH}")"
  curl_auth -X POST \
    "${BASE_URL}/api/eval/benchmark/capability-baseline/refresh?limit=${LIMIT}&baseline_path=${ENCODED_PATH}"
  echo ""
else
  echo "Server unreachable — falling back to benchmark_baselines.py CLI"
  "${PYTHON_BIN}" "${ROOT}/scripts/benchmark_baselines.py" \
    --refresh-capability-baseline \
    --capability-limit "${LIMIT}" \
    --capability-baseline-out "${BASELINE_PATH}"
fi

if [[ -f "${BASELINE_PATH}" ]]; then
  echo "OK — baseline refreshed: ${BASELINE_PATH}"
else
  echo "WARN: baseline file not found after refresh" >&2
  exit 1
fi
