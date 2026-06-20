#!/usr/bin/env bash
# Prod readiness: plan dev green + GPU/cloud preflight + optional staging/prod beta gates.
# Не делает git push; для real prod нужны секреты (см. gpu_dpo_preflight).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"

RUN_STAGING="${TERMIT_PROD_READINESS_STAGING:-auto}"
DEV_SEED="${TERMIT_PROD_READINESS_DEV_SEED:-false}"
STRICT_GPU="${TERMIT_PROD_READINESS_STRICT_GPU:-false}"
HOSTED_URL="${TERMIT_HOSTED_BASE_URL:-http://127.0.0.1:8080}"

PREFLIGHT_BLOCKER=0
STAGING_FAILED=0
PROD_BETA_FAILED=0

echo "== Termit prod readiness check (staging=${RUN_STAGING}, dev_seed=${DEV_SEED}) =="

echo ""
echo "== 1/4 Plan status (relax env) =="
PLAN_ARGS=(--summary-only)
if [[ "${TERMIT_PROD_READINESS_CI:-}" != "true" ]]; then
  PLAN_ARGS+=(--strict)
fi
if [[ "${DEV_SEED}" == "true" ]]; then
  "${ROOT}/scripts/plan_status_dev_green.sh"
else
  TERMIT_PLAN_STATUS_LOCAL=true \
  TERMIT_PLAN_STATUS_RELAX_ENV_WARNINGS=true \
    "${PYTHON_BIN}" "${ROOT}/scripts/plan_status_check.py" "${PLAN_ARGS[@]}"
fi

echo ""
echo "== 2/5 GPU / cloud preflight =="
if ! "${ROOT}/scripts/gpu_dpo_preflight.sh"; then
  PREFLIGHT_BLOCKER=1
  if [[ "${STRICT_GPU}" == "true" ]]; then
    echo "STRICT_GPU: preflight blocker — exit 1." >&2
    exit 1
  fi
  echo "WARN: GPU/cloud preflight blockers (non-fatal unless TERMIT_PROD_READINESS_STRICT_GPU=true)."
fi

if [[ "${TERMIT_PROD_READINESS_PHASE0:-true}" == "true" ]]; then
  echo ""
  echo "== 2b/5 Phase 0 V4 readiness (non-strict) =="
  TERMIT_PHASE0_STRICT=false \
  TERMIT_PHASE0_RUN_BENCHMARK=false \
    "${ROOT}/scripts/phase0_v4_readiness.sh" || echo "WARN: phase0 readiness reported gaps."
fi

STAGING_RUN=false
if [[ "${RUN_STAGING}" == "true" ]]; then
  STAGING_RUN=true
elif [[ "${RUN_STAGING}" == "auto" ]]; then
  if curl -sf --max-time 3 "${HOSTED_URL}/health" >/dev/null 2>&1; then
    STAGING_RUN=true
    echo ""
    echo "Hosted ${HOSTED_URL} доступен — включим staging gate."
  fi
fi

if [[ "${STAGING_RUN}" == "true" ]]; then
  echo ""
  echo "== 3/5 Staging gate (${HOSTED_URL}) =="
  if TERMIT_HOSTED_BASE_URL="${HOSTED_URL}" "${ROOT}/scripts/release_gate_staging.sh"; then
    echo "OK — staging gate."
  else
    STAGING_FAILED=1
    echo "WARN: staging gate failed." >&2
  fi
else
  echo ""
  echo "== 3/5 Staging gate — skip (TERMIT_PROD_READINESS_STAGING=${RUN_STAGING}) =="
fi

if [[ -n "${TERMIT_BETA_PROD_URL:-${TERMIT_HOSTED_PROD_URL:-}}" ]]; then
  echo ""
  echo "== 4/5 Prod beta gate =="
  if "${ROOT}/scripts/beta_prod_gate.sh"; then
    echo "OK — prod beta gate."
  else
    PROD_BETA_FAILED=1
    echo "WARN: prod beta gate failed." >&2
  fi
else
  echo ""
  echo "== 4/5 Prod beta gate — skip (задайте TERMIT_BETA_PROD_URL) =="
fi

echo ""
if [[ "${PREFLIGHT_BLOCKER}" -eq 1 ]]; then
  echo "Prod blockers (GPU/cloud): см. вывод gpu_dpo_preflight.sh выше."
fi
if [[ "${STAGING_FAILED}" -eq 1 || "${PROD_BETA_FAILED}" -eq 1 ]]; then
  echo "FAIL — staging or prod beta gate failed." >&2
  exit 1
fi

if [[ "${PREFLIGHT_BLOCKER}" -eq 1 ]]; then
  echo "OK — local readiness gates passed; real prod blockers remain (GPU/cloud/prod URL)."
  exit 0
fi

echo "OK — prod readiness check passed (local + preflight green)."
