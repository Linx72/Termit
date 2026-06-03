#!/usr/bin/env bash
# Full automatic setup: do_all_setup + LaunchAgent + schedulers + automation flags in .env.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== Termit do_all_automatic =="

set_env_key() {
  local key="$1"
  local val="$2"
  local file="${3:-${ROOT}/.env}"
  if [[ ! -f "${file}" ]]; then
    cp "${ROOT}/.env.example" "${file}"
    echo "Created ${file} from .env.example"
  fi
  if grep -q "^${key}=" "${file}"; then
    if [[ "$(uname -s)" == "Darwin" ]]; then
      sed -i '' "s|^${key}=.*|${key}=${val}|" "${file}"
    else
      sed -i "s|^${key}=.*|${key}=${val}|" "${file}"
    fi
  else
    echo "${key}=${val}" >> "${file}"
  fi
}

install_weekly_eval_cron() {
  local marker="# termit-weekly-eval"
  local cmd="cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/weekly_eval.sh >> ${HOME}/Library/Logs/termit-weekly-eval.log 2>&1"
  if [[ "$(uname -s)" == "Linux" ]]; then
    cmd="cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/weekly_eval.sh >> ${HOME}/termit-weekly-eval.log 2>&1"
  fi
  local line="0 4 * * 1 ${cmd} ${marker}"
  ( { crontab -l 2>/dev/null || true; } | grep -v "${marker}" || true; echo "${line}" ) | crontab -
  echo "Weekly eval crontab (Mon 04:00): ${line}"
}

install_daily_improvement_cron() {
  local marker="# termit-daily-improvement"
  local cmd="cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/daily_improvement.sh >> ${HOME}/Library/Logs/termit-daily-improvement.log 2>&1"
  if [[ "$(uname -s)" == "Linux" ]]; then
    cmd="cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/daily_improvement.sh >> ${HOME}/termit-daily-improvement.log 2>&1"
  fi
  local line="5 2 * * * ${cmd} ${marker}"
  ( { crontab -l 2>/dev/null || true; } | grep -v "${marker}" || true; echo "${line}" ) | crontab -
  echo "Daily improvement crontab (02:05 local): ${line}"
}

echo "== 1/5 Base setup (venv, tests, clients, LaunchAgent) =="
TERMIT_INSTALL_LAUNCH_AGENT=1 "${ROOT}/scripts/do_all_setup.sh"

echo ""
echo "== 2/5 Automation flags in .env =="
set_env_key TERMIT_STAGE1_SCHEDULE_ENABLED true
set_env_key TERMIT_STAGE1_SCHEDULE_BASE_MODEL "ollama:deepseek-coder"
set_env_key TERMIT_RETRIEVAL_AUTO_REINDEX true
set_env_key TERMIT_AGENT_SCHEDULES_ENABLED true
set_env_key TERMIT_AGENT_MAINTENANCE_ENABLED true
set_env_key TERMIT_FINETUNE_AUTO_CAPTURE_SIGNALS true
set_env_key TERMIT_DAILY_IMPROVEMENT_ENABLED true
set_env_key TERMIT_AUTO_START_OLLAMA true
set_env_key TERMIT_EVAL_CI_LIMIT 53
echo "Updated ${ROOT}/.env (builtin Stage1 scheduler, auto reindex, agent schedules, signal capture)."

echo ""
echo "== 3/5 Restart API (load .env) =="
"${ROOT}/scripts/restart_server.sh"

echo ""
echo "== 4/5 External schedulers =="
if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "Stage1: using built-in scheduler inside Termit (LaunchAgent keeps API up)."
  echo "Optional external LaunchAgent skipped to avoid duplicate weekly runs."
  echo "  To add external instead: TERMIT_STAGE1_SCHEDULE_ENABLED=false && ./scripts/install_stage1_scheduler.sh launchd"
  install_weekly_eval_cron
  install_daily_improvement_cron
else
  "${ROOT}/scripts/install_stage1_scheduler.sh" cron || true
  install_weekly_eval_cron
  install_daily_improvement_cron
fi

echo ""
echo "== 5/5 Smoke =="
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate"
"${ROOT}/scripts/smoke_http.sh"

echo ""
echo "== Scheduler status =="
curl -sf "http://127.0.0.1:8765/api/finetune/pipeline/stage1-scheduler/status" \
  | "${ROOT}/.venv/bin/python" -m json.tool 2>/dev/null || echo "(stage1 scheduler status unavailable)"

curl -sf "http://127.0.0.1:8765/api/ops/daily-improvement/status" \
  | "${ROOT}/.venv/bin/python" -m json.tool 2>/dev/null || echo "(daily improvement status unavailable)"

echo ""
echo "Done — automatic mode."
echo "  API (login):     LaunchAgent com.termit.server → http://127.0.0.1:8765"
echo "  Stage1 pipeline: builtin, Mon 03:00 UTC (TERMIT_STAGE1_SCHEDULE_*)"
echo "  Daily improve:   builtin 02:00 UTC + crontab 02:05 → scripts/daily_improvement.sh"
echo "  Weekly eval:     crontab Mon 04:00 local → scripts/weekly_eval.sh"
echo "  Agent schedules: TERMIT_AGENT_SCHEDULES_ENABLED=true"
echo "  Desktop:         ${ROOT}/clients/termit-desktop/release/mac-arm64/Termit.app"
echo "  Uninstall API:   ./scripts/uninstall_launch_agent.sh"
