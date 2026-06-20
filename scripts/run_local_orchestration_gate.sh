#!/usr/bin/env bash
# Enable tool-loop execution, verify running server config, run local orchestration gate.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
if [[ -f "${ROOT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT}/.venv/bin/activate"
fi

_fetch_orch_config() {
  TERMIT_BASE_URL="${BASE_URL}" "${PYTHON_BIN}" - <<'PY'
import json
import os
import urllib.request

base = os.environ.get("TERMIT_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
with urllib.request.urlopen(f"{base}/api/orchestration/config", timeout=10) as resp:
    print(resp.read().decode("utf-8"))
PY
}

_orch_config_bool() {
  local key="$1"
  echo "${CONFIG_JSON}" | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin).get('${key}', False))"
}

echo "== Local orchestration tool-loop gate =="

"${ROOT}/scripts/enable_orchestration_tool_loop.sh"
USE_FIXTURE_SPIKE="${TERMIT_ORCH_SPIKE_USE_FIXTURE:-true}"
if [[ "${TERMIT_ORCH_SKIP_SERVER_RESTART:-false}" != "true" ]]; then
  echo "Applying orchestration config (restart)..."
  "${ROOT}/scripts/restart_server.sh" >/dev/null
  sleep 2
else
  echo "Skip server restart (TERMIT_ORCH_SKIP_SERVER_RESTART=true)."
fi

if ! curl -sf --max-time 5 "${BASE_URL}/health" >/dev/null 2>&1; then
  echo "Termit API not reachable at ${BASE_URL}" >&2
  echo "Start server: ./scripts/restart_server.sh" >&2
  exit 1
fi

CONFIG_JSON="$(_fetch_orch_config)"

echo "Server orchestration config: ${CONFIG_JSON}"

TOOL_LOOP_ENABLED="$(_orch_config_bool tool_loop_execution_enabled)"
FIXTURE_CODER_ENABLED="$(_orch_config_bool eval_fixture_coder_enabled)"
CONFIG_STALE=false
if [[ "${TOOL_LOOP_ENABLED}" != "True" && "${TOOL_LOOP_ENABLED}" != "true" ]]; then
  CONFIG_STALE=true
fi
if [[ "${USE_FIXTURE_SPIKE}" == "true" ]] && [[ "${FIXTURE_CODER_ENABLED}" != "True" && "${FIXTURE_CODER_ENABLED}" != "true" ]]; then
  CONFIG_STALE=true
fi

if [[ "${CONFIG_STALE}" == "true" ]]; then
  if [[ "${TERMIT_ORCH_SKIP_SERVER_RESTART:-false}" == "true" ]]; then
    echo "WARN: orchestration config stale on running server — restart required for fixture/live gate."
  else
    echo "WARN: orchestration config stale on running server — restarting..."
  fi
  "${ROOT}/scripts/restart_server.sh" >/dev/null
  sleep 2
  CONFIG_JSON="$(_fetch_orch_config)"
  echo "Server orchestration config after restart: ${CONFIG_JSON}"
  TOOL_LOOP_ENABLED="$(_orch_config_bool tool_loop_execution_enabled)"
  FIXTURE_CODER_ENABLED="$(_orch_config_bool eval_fixture_coder_enabled)"
  if [[ "${TOOL_LOOP_ENABLED}" != "True" && "${TOOL_LOOP_ENABLED}" != "true" ]]; then
    echo "WARN: tool_loop_execution_enabled still false after restart." >&2
    if [[ "${TERMIT_LOCAL_ORCH_ALLOW_STALE_CONFIG:-false}" != "true" ]]; then
      exit 1
    fi
  fi
  if [[ "${USE_FIXTURE_SPIKE}" == "true" ]] && [[ "${FIXTURE_CODER_ENABLED}" != "True" && "${FIXTURE_CODER_ENABLED}" != "true" ]]; then
    echo "WARN: eval_fixture_coder_enabled still false after restart (fixture spike requires it)." >&2
    if [[ "${TERMIT_LOCAL_ORCH_ALLOW_STALE_CONFIG:-false}" != "true" ]]; then
      exit 1
    fi
  fi
fi

if [[ "${TERMIT_ORCH_LOCAL_SKIP_SPIKE:-false}" == "true" ]]; then
  echo "== Offline preflight (unit smoke only, skip live spike) =="
  "${ROOT}/scripts/orchestration_tool_loop_smoke.sh"
  echo ""
  echo "OK — local orchestration preflight passed (spike skipped)."
  exit 0
fi

OUTPUT="${TERMIT_ORCH_LOCAL_REPORT:-/tmp/orch_eval_report_local.json}"
export TERMIT_ORCH_GATE_TIER="${TERMIT_ORCH_GATE_TIER:-local}"
export TERMIT_ORCH_REQUIRE_TOOL_LOOP=true
export TERMIT_ORCH_MIN_TOOL_LOOP_STEPS=1
export TERMIT_ORCH_SPIKE_USE_FIXTURE="${TERMIT_ORCH_SPIKE_USE_FIXTURE:-true}"

"${PYTHON_BIN}" "${ROOT}/scripts/eval_orchestration_spike.py" \
  --base-url "${BASE_URL}" \
  --prompts-file "${ROOT}/data/eval_scenarios_orchestration.json" \
  --tool-loop-only \
  --max-prompts "${TERMIT_ORCH_SPIKE_MAX_PROMPTS:-1}" \
  --timeout-seconds "${TERMIT_ORCH_SPIKE_TIMEOUT_SECONDS:-180}" \
  --min-pass-rate "${TERMIT_ORCH_SPIKE_MIN_PASS_RATE:-0.0}" \
  --output-file "${OUTPUT}" \
  --append-report-file "${ROOT}/data/orchestration_eval_reports.jsonl"

TERMIT_ORCH_GATE_TIER="${TERMIT_ORCH_GATE_TIER:-local}" \
  "${PYTHON_BIN}" "${ROOT}/scripts/eval_orchestration_gate.py" < "${OUTPUT}"

echo ""
echo "OK — local orchestration gate passed (report: ${OUTPUT})"
