#!/usr/bin/env bash
# Prod beta gate: D30 cohort ≥ N, retention ≥ 35%, product KPI gates (без dev seed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

BASE_URL="${TERMIT_BETA_PROD_URL:-${TERMIT_HOSTED_PROD_URL:-}}"
if [[ -z "${BASE_URL}" ]]; then
  echo "Задайте TERMIT_BETA_PROD_URL или TERMIT_HOSTED_PROD_URL (prod API base)." >&2
  exit 1
fi

API_KEY="${TERMIT_API_KEY:-${TERMIT_HOSTED_API_KEY:-}}"
MIN_COHORT="${TERMIT_BETA_MIN_COHORT_D30:-5}"
STRICT="${TERMIT_BETA_PROD_STRICT:-true}"
OUTPUT="${TERMIT_BETA_PROD_REPORT:-${ROOT}/data/beta_prod_gate_last.json}"

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate" 2>/dev/null || true

echo "== Beta prod gate (${BASE_URL}, gate_mode=prod, min_cohort_d30=${MIN_COHORT}) =="

if ! curl -sf --max-time 10 "${BASE_URL}/health" >/dev/null 2>&1; then
  echo "Prod API недоступен: ${BASE_URL}" >&2
  exit 1
fi

ARGS=(
  --base-url "${BASE_URL}"
  --min-cohort-d30 "${MIN_COHORT}"
  --gate-mode prod
  --require-product-gates true
  --reject-dev-seed
  --output "${OUTPUT}"
)
if [[ -n "${API_KEY}" ]]; then
  ARGS+=(--api-key "${API_KEY}")
fi
if [[ "${STRICT}" == "true" ]]; then
  ARGS+=(--strict)
fi

export TERMIT_BETA_USE_LOCAL_META=false

if ! TERMIT_BETA_USE_LOCAL_META=false "${PYTHON_BIN}" "${ROOT}/scripts/beta_telemetry_report.py" "${ARGS[@]}"; then
  echo "Beta prod gate FAILED (strict=${STRICT})." >&2
  exit 1
fi

echo ""
echo "OK — beta prod gate passed."
echo "  Report: ${OUTPUT}"
