#!/usr/bin/env bash
# Локальный dev: seed KPI + plan status с overall_ok=true (relax GPU/cloud env warnings).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
"${ROOT}/scripts/local_dev_kpi_seed.sh"

echo ""
echo "== Strict plan check (expect overall_ok) =="
TERMIT_PLAN_STATUS_LOCAL=true \
TERMIT_PLAN_STATUS_RELAX_ENV_WARNINGS=true \
  "${PYTHON_BIN}" "${ROOT}/scripts/plan_status_check.py" --summary-only --strict

echo "OK — plan status dev green."
