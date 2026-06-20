#!/usr/bin/env bash
# Staging/hosted beta gate: cohort D30 ≥ N + desktop KPI gates green.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

BASE_URL="${TERMIT_HOSTED_BASE_URL:-${TERMIT_BASE_URL:-http://127.0.0.1:8080}}"
API_KEY="${TERMIT_API_KEY:-${TERMIT_HOSTED_API_KEY:-}}"
MIN_COHORT="${TERMIT_BETA_MIN_COHORT_D30:-5}"
GATE_MODE="${TERMIT_BETA_GATE_MODE:-d30}"
MIN_TRACKED="${TERMIT_BETA_MIN_TRACKED:-5}"
MIN_ACTIVE="${TERMIT_BETA_MIN_ACTIVE_7D:-3}"
REQUIRE_GATES="${TERMIT_BETA_REQUIRE_PRODUCT_GATES:-true}"
STRICT="${TERMIT_BETA_STAGING_STRICT:-true}"
OUTPUT="${TERMIT_BETA_STAGING_REPORT:-${ROOT}/data/beta_staging_gate_last.json}"

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate" 2>/dev/null || true

echo "== Beta staging gate (${BASE_URL}, min_cohort_d30=${MIN_COHORT}) =="

if ! curl -sf --max-time 5 "${BASE_URL}/health" >/dev/null 2>&1; then
  echo "API недоступен: ${BASE_URL}" >&2
  exit 1
fi

ARGS=(
  --base-url "${BASE_URL}"
  --min-cohort-d30 "${MIN_COHORT}"
  --gate-mode "${GATE_MODE}"
  --min-tracked "${MIN_TRACKED}"
  --min-active-7d "${MIN_ACTIVE}"
  --require-product-gates "${REQUIRE_GATES}"
  --output "${OUTPUT}"
)
if [[ -n "${API_KEY}" ]]; then
  ARGS+=(--api-key "${API_KEY}")
fi
if [[ "${STRICT}" == "true" ]]; then
  ARGS+=(--strict)
fi

if ! "${PYTHON_BIN}" "${ROOT}/scripts/beta_telemetry_report.py" "${ARGS[@]}"; then
  echo "Beta staging gate FAILED (strict=${STRICT})." >&2
  exit 1
fi

echo ""
echo "OK — beta staging gate passed."
echo "  Report: ${OUTPUT}"
