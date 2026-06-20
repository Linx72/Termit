#!/usr/bin/env bash
# Локальный dev: seed beta + product KPI и показать plan status (не для prod).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate" 2>/dev/null || true

export TERMIT_BETA_DEV_SEED=true
export TERMIT_PRODUCT_KPI_DEV_SEED=true

echo "== Beta cohort dev seed =="
"${PYTHON_BIN}" "${ROOT}/scripts/seed_beta_cohort_dev.py" --force

echo ""
echo "== Product KPI dev seed =="
"${PYTHON_BIN}" "${ROOT}/scripts/seed_product_kpi_dev.py" --force

echo ""
echo "== Plan status (summary) =="
"${PYTHON_BIN}" "${ROOT}/scripts/plan_status_check.py" --summary-only
