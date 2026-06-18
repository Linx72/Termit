#!/usr/bin/env bash
# Full weekly cycle: normalize signals → training loop → closed-loop gates.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate" 2>/dev/null || true

echo "== Termit weekly full cycle =="

AUTO_TRAIN="${TERMIT_FINETUNE_AUTO_TRAIN:-false}"
if [[ "${TERMIT_CAPTURE_KPI_BASELINE:-true}" == "true" && "${AUTO_TRAIN}" != "true" ]]; then
  echo "== 0/4 Capture eval KPI baseline (pre-train, cursor_parity) =="
  TERMIT_EVAL_KPI_BASELINE="${TERMIT_EVAL_KPI_BASELINE:-${ROOT}/data/eval_kpi_baseline.json}" \
    TERMIT_EVAL_LIMIT="${TERMIT_EVAL_LIMIT:-20}" \
    "${ROOT}/scripts/capture_eval_kpi_baseline.sh"
elif [[ "${AUTO_TRAIN}" == "true" ]]; then
  echo "== 0/4 Skip cursor_parity KPI capture (model KPI baseline in training_loop_full) =="
fi

echo "== 1/4 Normalize training signals =="
"${PYTHON_BIN}" "${ROOT}/scripts/normalize_training_signals.py"

echo ""
echo "== 2/4 Training loop (full) =="
TERMIT_EVAL_AUTO_PROMOTE_BASELINE="${TERMIT_EVAL_AUTO_PROMOTE_BASELINE:-false}" \
  "${ROOT}/scripts/training_loop_full.sh"

echo ""
echo "== 3/4 Weekly closed-loop gates (eval + shadow + orchestration) =="
TERMIT_WEEKLY_RUN_TRAINING_LOOP=false \
  "${ROOT}/scripts/weekly_closed_loop.sh"

echo ""
echo "OK — weekly full cycle complete."
