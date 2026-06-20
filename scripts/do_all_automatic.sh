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
  local cmd="cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/weekly_closed_loop.sh >> ${HOME}/Library/Logs/termit-weekly-closed-loop.log 2>&1"
  if [[ "$(uname -s)" == "Linux" ]]; then
    cmd="cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/weekly_closed_loop.sh >> ${HOME}/termit-weekly-closed-loop.log 2>&1"
  fi
  local line="0 4 * * 1 ${cmd} ${marker}"
  _install_crontab_line "${marker}" "${line}" "Weekly closed loop crontab (Mon 04:00)"
}

install_quarterly_capability_cron() {
  local marker="# termit-quarterly-capability"
  local cmd="cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/quarterly_capability.sh >> ${HOME}/Library/Logs/termit-quarterly-capability.log 2>&1"
  if [[ "$(uname -s)" == "Linux" ]]; then
    cmd="cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/quarterly_capability.sh >> ${HOME}/termit-quarterly-capability.log 2>&1"
  fi
  local line="0 5 1 1,4,7,10 * ${cmd} ${marker}"
  _install_crontab_line "${marker}" "${line}" "Quarterly capability crontab (1st of Jan/Apr/Jul/Oct 05:00)"
}

install_training_loop_cron() {
  local marker="# termit-training-loop-weekly"
  local log="${HOME}/Library/Logs/termit-training-loop-weekly.cron.log"
  local cmd="cd ${ROOT} && source ${ROOT}/.venv/bin/activate && TERMIT_WEEKLY_TRAINING_LOOP=true TERMIT_EVAL_AUTO_PROMOTE_BASELINE=true ${ROOT}/scripts/training_loop_weekly.sh >> ${log} 2>&1"
  if [[ "$(uname -s)" == "Linux" ]]; then
    log="${HOME}/termit-training-loop-weekly.cron.log"
    cmd="cd ${ROOT} && source ${ROOT}/.venv/bin/activate && TERMIT_WEEKLY_TRAINING_LOOP=true TERMIT_EVAL_AUTO_PROMOTE_BASELINE=true ${ROOT}/scripts/training_loop_weekly.sh >> ${log} 2>&1"
  fi
  local line="0 4 * * 0 ${cmd} ${marker}"
  _install_crontab_line "${marker}" "${line}" "Weekly training loop crontab (Sun 04:00)"
}

install_daily_improvement_cron() {
  local marker="# termit-daily-improvement"
  local cmd="cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/daily_improvement.sh >> ${HOME}/Library/Logs/termit-daily-improvement.log 2>&1"
  if [[ "$(uname -s)" == "Linux" ]]; then
    cmd="cd ${ROOT} && source ${ROOT}/.venv/bin/activate && ${ROOT}/scripts/daily_improvement.sh >> ${HOME}/termit-daily-improvement.log 2>&1"
  fi
  local line="5 2 * * * ${cmd} ${marker}"
  _install_crontab_line "${marker}" "${line}" "Daily improvement crontab (02:05 local)"
}

# macOS may hang crontab without Full Disk Access — use temp file + timeout.
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
    echo "warning: ${label} — crontab timed out (grant Full Disk Access to Terminal on macOS)" >&2
    rm -f "${tmp}"
    return 0
  fi
  if wait "${cpid}"; then
    echo "${label}: ${line}"
  else
    echo "warning: ${label} — crontab failed (optional; builtin schedulers still active)" >&2
  fi
  rm -f "${tmp}"
}

echo "== 1/6 Base setup (venv, tests, clients, LaunchAgent) =="
TERMIT_SKIP_SETUP_TESTS=1 TERMIT_INSTALL_LAUNCH_AGENT=1 "${ROOT}/scripts/do_all_setup.sh"

echo ""
echo "== 2/6 Automation flags in .env =="
set_env_key TERMIT_STAGE1_SCHEDULE_ENABLED true
set_env_key TERMIT_STAGE1_SCHEDULE_BASE_MODEL "ollama:qwen2.5-coder:14b"
set_env_key TERMIT_CODE_FALLBACK_MODEL "ollama:qwen2.5-coder:14b"
set_env_key TERMIT_DUAL_PASS_ENABLED true
set_env_key TERMIT_RETRIEVAL_AUTO_REINDEX true
set_env_key TERMIT_AGENT_SCHEDULES_ENABLED true
set_env_key TERMIT_AGENT_MAINTENANCE_ENABLED true
set_env_key TERMIT_FINETUNE_AUTO_CAPTURE_SIGNALS true
set_env_key TERMIT_FINETUNE_AUTO_TRAIN true
set_env_key TERMIT_FINETUNE_SHADOW_TRAFFIC_PERCENT 10
set_env_key TERMIT_ORCH_TOOL_LOOP_EXECUTION_ENABLED true
set_env_key TERMIT_ORCH_EVAL_FIXTURE_CODER true
set_env_key TERMIT_ORCH_TOOL_LOOP_FALLBACK true
set_env_key TERMIT_ORCH_GATE_TIER ci
set_env_key TERMIT_ROUTING_COST_AWARE_ENABLED true
set_env_key TERMIT_MAX_COST_PER_SUCCESSFUL_TASK_USD 1.0
set_env_key TERMIT_DAILY_IMPROVEMENT_ENABLED true
set_env_key TERMIT_SKILL_AUTO_SELECT_ENABLED true
set_env_key TERMIT_AUTO_START_OLLAMA true
set_env_key TERMIT_EVAL_CI_LIMIT 53
echo "Updated ${ROOT}/.env (builtin Stage1 scheduler, auto reindex, agent schedules, signal capture)."

echo ""
echo "== 3/6 Restart API (load .env) =="
"${ROOT}/scripts/restart_server.sh"

echo ""
echo "== 4/6 External schedulers =="
if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "Stage1: using built-in scheduler inside Termit (LaunchAgent keeps API up)."
  echo "Optional external LaunchAgent skipped to avoid duplicate weekly runs."
  echo "  To add external instead: TERMIT_STAGE1_SCHEDULE_ENABLED=false && ./scripts/install_stage1_scheduler.sh launchd"
else
  "${ROOT}/scripts/install_stage1_scheduler.sh" cron || true
fi
"${ROOT}/scripts/install_automation_crontabs.sh" || true

echo ""
echo "== 5/6 Smoke + automation status =="
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate"
"${ROOT}/scripts/smoke_http.sh"

curl -sf "http://127.0.0.1:8765/api/ops/automation" \
  | "${ROOT}/.venv/bin/python" -m json.tool 2>/dev/null | head -40 || echo "(automation status unavailable)"

echo ""
echo "== 6/6 Do-all verify (CI mode) =="
TERMIT_DO_ALL_CI=true "${ROOT}/scripts/do_all_verify_ci.sh"

if [[ "${TERMIT_DO_ALL_PLAN:-false}" == "true" ]]; then
  echo ""
  echo "== 7/7 Do-all plan (фаза 5) =="
  if [[ -f "${ROOT}/.env" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "${ROOT}/.env"
    set +a
  fi
  TERMIT_PLAN_TRY_STRICT_LIVE="${TERMIT_PLAN_TRY_STRICT_LIVE:-false}" \
    "${ROOT}/scripts/do_all_plan.sh"
  TERMIT_DO_ALL_DEPLOY_HOSTED="${TERMIT_DO_ALL_DEPLOY_HOSTED:-true}"
fi

_ensure_docker_daemon() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  if command -v colima >/dev/null 2>&1; then
    echo "Docker недоступен — пробуем colima start..."
    colima start >/dev/null 2>&1 || colima start
    sleep 5
    docker info >/dev/null 2>&1 && return 0
  fi
  return 1
}

if [[ "${TERMIT_DO_ALL_SKIP_HOSTED:-false}" != "true" ]]; then
  echo ""
  echo "== 8/8 Hosted smoke (Caddy :8080) =="
  if ! _ensure_docker_daemon; then
    echo "Skip — Docker daemon недоступен (Docker Desktop / Colima: ./scripts/deploy_hosted_beta.sh)"
  else
    BASE_HOSTED="${TERMIT_HOSTED_BASE_URL:-http://127.0.0.1:8080}"
    if ! curl -sf --max-time 3 "${BASE_HOSTED}/health" >/dev/null 2>&1; then
      if [[ "${TERMIT_DO_ALL_DEPLOY_HOSTED:-false}" == "true" ]]; then
        echo "Hosted proxy down — запуск deploy_hosted_beta.sh..."
        TERMIT_HOSTED_BASE_URL="${BASE_HOSTED}" "${ROOT}/scripts/deploy_hosted_beta.sh" \
          || echo "WARN: deploy_hosted_beta failed (non-blocking)."
      else
        echo "Skip — hosted proxy down (TERMIT_DO_ALL_DEPLOY_HOSTED=true или ./scripts/deploy_hosted_beta.sh)"
      fi
    fi
    if curl -sf --max-time 3 "${BASE_HOSTED}/health" >/dev/null 2>&1; then
      TERMIT_HOSTED_BASE_URL="${BASE_HOSTED}" \
        "${ROOT}/scripts/hosted_smoke.sh" \
        || echo "WARN: hosted smoke failed (non-blocking)."
    fi
  fi
fi

echo ""
echo "== Scheduler status =="
curl -sf "http://127.0.0.1:8765/api/finetune/pipeline/stage1-scheduler/status" \
  | "${ROOT}/.venv/bin/python" -m json.tool 2>/dev/null || echo "(stage1 scheduler status unavailable)"

curl -sf "http://127.0.0.1:8765/api/ops/daily-improvement/status" \
  | "${ROOT}/.venv/bin/python" -m json.tool 2>/dev/null || echo "(daily improvement status unavailable)"

curl -sf -X POST "http://127.0.0.1:8765/api/platform/skills/select" \
  -H "Content-Type: application/json" \
  -d '{"instruction":"Fix GitHub Actions CI and add pytest tests","task_type":"coding"}' \
  | "${ROOT}/.venv/bin/python" -m json.tool 2>/dev/null | head -20 || echo "(skill select unavailable)"

echo ""
echo "Done — automatic mode."
echo "  Desktop toggles: Termit.app sidebar → «Автоматизация сервера» (PATCH /api/ops/automation)"
echo "  API (login):     LaunchAgent com.termit.server → http://127.0.0.1:8765"
echo "  Stage1 pipeline: builtin, Mon 03:00 UTC (TERMIT_STAGE1_SCHEDULE_*)"
echo "  Daily improve:   builtin 02:00 UTC + crontab 02:05 → scripts/daily_improvement.sh"
echo "  Skill auto-select: TERMIT_SKILL_AUTO_SELECT_ENABLED=true (max 3 skills/run)"
echo "  Weekly loop:     crontab Mon 04:00 local → scripts/weekly_closed_loop.sh"
echo "  Training loop:   crontab Sun 04:00 local → scripts/training_loop_weekly.sh (incl. signal normalize)"
echo "  Full cycle:      manual → scripts/weekly_full_cycle.sh (normalize + train + gates)"
echo "  DPO GPU train:   scripts/dpo_gpu_train.sh (dry-run fallback without GPU)"
echo "  Cap baseline:    scripts/capability_baseline_refresh.sh"
echo "  Cloud benchmark: scripts/cloud_benchmark_cycle.sh"
echo "  Orch live gate:  scripts/run_live_orchestration_gate.sh"
echo "  Do-all verify:   scripts/do_all_verify.sh"
echo "  Do-all CI:       scripts/do_all_verify_ci.sh"
echo "  Do-all full:     scripts/do_all_verify_full.sh"
echo "  Do-all plan:     scripts/do_all_plan.sh"
echo "  Deploy hosted:   scripts/deploy_hosted_beta.sh"
echo "  SWE eval gate:   scripts/swe_eval_gate.py"
echo "  Beta dev seed:   TERMIT_BETA_DEV_SEED=true scripts/seed_beta_cohort_dev.py"
echo "  Product KPI dev: TERMIT_PRODUCT_KPI_DEV_SEED=true scripts/seed_product_kpi_dev.py"
echo "  Local KPI bundle: ./scripts/local_dev_kpi_seed.sh"
echo "  DPO contract:    scripts/do_all_dpo_contract.sh"
echo "  macOS live orch: scripts/nightly_macos_live_orchestration.sh"
echo "  Strict live orch: scripts/run_strict_live_orchestration_gate.sh"
echo "  KPI baseline:    scripts/capture_eval_kpi_baseline.sh"
echo "  Crontab install: scripts/install_automation_crontabs.sh"
echo "  Ollama CI boot:  scripts/bootstrap_ollama_ci.sh"
echo "  Orchestration:   TERMIT_ORCH_TOOL_LOOP_EXECUTION_ENABLED=true (tier ci; local: run_local_orchestration_gate.sh)"
echo "  Cost routing:    TERMIT_ROUTING_COST_AWARE_ENABLED=true"
echo "  Quarterly cap:   crontab 1st Jan/Apr/Jul/Oct 05:00 → scripts/quarterly_capability.sh"
echo "  Agent schedules: TERMIT_AGENT_SCHEDULES_ENABLED=true"
echo "  Desktop:         ${ROOT}/clients/termit-desktop/release/mac-arm64/Termit.app"
echo "  Uninstall API:   ./scripts/uninstall_launch_agent.sh"
