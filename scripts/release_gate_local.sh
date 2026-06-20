#!/usr/bin/env bash
# Локальный release gate: extended smoke + plan status dev green (overall_ok).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"

PROFILE="${TERMIT_RELEASE_SMOKE_PROFILE:-extended}"
STAGING="${TERMIT_RELEASE_RUN_STAGING:-false}"
STRICT_PLAN="${TERMIT_RELEASE_PLAN_STRICT:-false}"

echo "== Release gate local (smoke=${PROFILE} + plan dev green${STAGING:+, staging}) =="

TERMIT_RELEASE_SMOKE_PROFILE="${PROFILE}" "${ROOT}/scripts/release_smoke.sh"

if [[ "${STRICT_PLAN}" == "true" ]]; then
  TERMIT_PLAN_STATUS_LOCAL=true \
  TERMIT_PLAN_STATUS_RELAX_ENV_WARNINGS=true \
    "${PYTHON_BIN}" "${ROOT}/scripts/plan_status_check.py" --summary-only --strict
else
  "${ROOT}/scripts/plan_status_dev_green.sh"
fi

if [[ "${STAGING}" == "true" ]]; then
  echo ""
  "${ROOT}/scripts/release_gate_staging.sh"
fi

echo "OK — release gate local passed."
