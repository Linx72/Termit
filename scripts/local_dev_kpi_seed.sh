#!/usr/bin/env bash
# Локальный dev: seed beta + product KPI + finetune KPI и показать plan status (не для prod).
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
export TERMIT_FINETUNE_KPI_DEV_SEED=true
export TERMIT_PLAN_STATUS_RELAX_ENV_WARNINGS=true

CHATS="${TERMIT_PRODUCT_KPI_CHATS:-12}"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"

echo "== Beta cohort dev seed =="
"${PYTHON_BIN}" "${ROOT}/scripts/seed_beta_cohort_dev.py" --force

echo ""
echo "== Finetune KPI dev seed =="
"${PYTHON_BIN}" "${ROOT}/scripts/seed_finetune_kpi_dev.py" --force

echo ""
echo "== Product KPI dev seed (tool-loop + workflow, без chat) =="
"${PYTHON_BIN}" "${ROOT}/scripts/seed_product_kpi_dev.py" --force --runs 10 --chats 0 --base-url "${BASE_URL}"

if curl -sf --max-time 3 "${BASE_URL}/health" >/dev/null 2>&1; then
  if [[ "${TERMIT_PRODUCT_KPI_LIVE_CHATS:-false}" == "true" ]]; then
    echo ""
    echo "== Live chat warm-up (${CHATS} запросов) =="
    "${PYTHON_BIN}" "${ROOT}/scripts/seed_product_kpi_dev.py" --force --runs 0 --local-runs 0 --chats "${CHATS}" --base-url "${BASE_URL}"
  else
    echo "Live chat warm-up пропущен (chat p95 из dev_chat_metrics_seed.json; TERMIT_PRODUCT_KPI_LIVE_CHATS=true для live)."
  fi
else
  echo "API недоступен — live reload пропущен (запустите ./scripts/restart_server.sh)."
fi

echo ""
echo "== Plan status (summary, local + relax env) =="
TERMIT_PLAN_STATUS_LOCAL=true "${PYTHON_BIN}" "${ROOT}/scripts/plan_status_check.py" --summary-only
