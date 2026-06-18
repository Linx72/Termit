#!/usr/bin/env bash
# Re-install external crontab lines from do_all_automatic (weekly/training/quarterly/daily).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

_install_crontab_line() {
  local marker="$1"
  local line="$2"
  local label="$3"
  local tmp cpid waited=0
  tmp="$(mktemp)"
  ( { crontab -l 2>/dev/null || true; } | grep -v "${marker}" || true; echo "${line}" ) > "${tmp}"
  crontab "${tmp}" &
  cpid=$!
  while kill -0 "${cpid}" 2>/dev/null && [[ "${waited}" -lt 10 ]]; do
    sleep 1
    waited=$((waited + 1))
  done
  if kill -0 "${cpid}" 2>/dev/null; then
    kill "${cpid}" 2>/dev/null || true
    echo "warning: ${label} — crontab timed out" >&2
    rm -f "${tmp}"
    return 1
  fi
  wait "${cpid}"
  rm -f "${tmp}"
  echo "${label}: installed"
}

LOG_DIR="$HOME/Library/Logs"
if [[ "$(uname -s)" == "Linux" ]]; then
  LOG_DIR="$HOME"
fi

echo "== Install automation crontabs =="

_install_crontab_line \
  "# termit-weekly-eval" \
  "0 4 * * 1 cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/weekly_closed_loop.sh >> ${LOG_DIR}/termit-weekly-closed-loop.log 2>&1 # termit-weekly-eval" \
  "weekly closed loop"

_install_crontab_line \
  "# termit-training-loop-weekly" \
  "0 4 * * 0 cd ${ROOT} && source ${ROOT}/.venv/bin/activate && TERMIT_WEEKLY_TRAINING_LOOP=true TERMIT_EVAL_AUTO_PROMOTE_BASELINE=true ${ROOT}/scripts/training_loop_weekly.sh >> ${LOG_DIR}/termit-training-loop-weekly.cron.log 2>&1 # termit-training-loop-weekly" \
  "training loop weekly"

_install_crontab_line \
  "# termit-quarterly-capability" \
  "0 5 1 1,4,7,10 * cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/quarterly_capability.sh >> ${LOG_DIR}/termit-quarterly-capability.log 2>&1 # termit-quarterly-capability" \
  "quarterly capability"

_install_crontab_line \
  "# termit-daily-improvement" \
  "5 2 * * * cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/daily_improvement.sh >> ${LOG_DIR}/termit-daily-improvement.log 2>&1 # termit-daily-improvement" \
  "daily improvement"

echo "OK — automation crontabs installed."
