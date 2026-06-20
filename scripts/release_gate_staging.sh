#!/usr/bin/env bash
# Release gate для hosted staging (:8080): smoke + real beta bootstrap + product gates.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

BASE_HOSTED="${TERMIT_HOSTED_BASE_URL:-http://127.0.0.1:8080}"
GATE_MODE="${TERMIT_BETA_GATE_MODE:-real}"
STRICT="${TERMIT_BETA_STAGING_STRICT:-true}"

cd "$ROOT"

echo "== Release gate staging (${BASE_HOSTED}, beta_gate=${GATE_MODE}) =="

if ! curl -sf --max-time 5 "${BASE_HOSTED}/health" >/dev/null 2>&1; then
  echo "Hosted staging недоступен: ${BASE_HOSTED}" >&2
  echo "Запуск: ./scripts/start_colima_and_deploy_beta.sh" >&2
  exit 1
fi

echo ""
echo "== 1/4 Hosted smoke =="
TERMIT_HOSTED_BASE_URL="${BASE_HOSTED}" "${ROOT}/scripts/hosted_smoke.sh"

echo ""
echo "== 2/5 Seed hosted product KPI =="
"${ROOT}/scripts/seed_hosted_product_kpi.sh" || echo "WARN: hosted KPI seed skipped."

echo ""
echo "== 3/5 Bootstrap real beta actors =="
"${PYTHON_BIN}" "${ROOT}/scripts/bootstrap_beta_staging_cohort.py" \
  --base-url "${BASE_HOSTED}" \
  --actors "${TERMIT_BETA_BOOTSTRAP_ACTORS:-5}"

echo ""
echo "== 4/5 Beta staging gate (${GATE_MODE}) =="
TERMIT_HOSTED_BASE_URL="${BASE_HOSTED}" \
TERMIT_BETA_GATE_MODE="${GATE_MODE}" \
TERMIT_BETA_REQUIRE_PRODUCT_GATES="${TERMIT_BETA_REQUIRE_PRODUCT_GATES:-true}" \
TERMIT_BETA_STAGING_STRICT="${STRICT}" \
  "${ROOT}/scripts/beta_staging_gate.sh"

echo ""
echo "== 5/5 Plan status snapshot (hosted) =="
TERMIT_BASE_URL="${BASE_HOSTED}" \
TERMIT_PLAN_STATUS_SNAPSHOT="${ROOT}/data/plan_status_staging.json" \
  "${ROOT}/scripts/capture_plan_status_snapshot.sh" || true

echo ""
echo "OK — release gate staging passed."
