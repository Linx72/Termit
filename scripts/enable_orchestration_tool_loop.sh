#!/usr/bin/env bash
# Enable orchestrator coder tool-loop execution + local orchestration gate tier.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="python3"
fi

touch "${ENV_FILE}"

set_env() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "${ENV_FILE}"; then
    if [[ "$(uname -s)" == "Darwin" ]]; then
      sed -i '' "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
    else
      sed -i "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
    fi
  else
    echo "${key}=${value}" >> "${ENV_FILE}"
  fi
}

set_env "TERMIT_ORCH_TOOL_LOOP_EXECUTION_ENABLED" "true"
if [[ "${TERMIT_ORCH_ENABLE_EVAL_FIXTURE:-true}" == "true" ]]; then
  set_env "TERMIT_ORCH_EVAL_FIXTURE_CODER" "true"
else
  set_env "TERMIT_ORCH_EVAL_FIXTURE_CODER" "false"
fi
set_env "TERMIT_ORCH_GATE_TIER" "local"
set_env "TERMIT_ORCH_REQUIRE_TOOL_LOOP" "true"
set_env "TERMIT_ORCH_MIN_TOOL_LOOP_STEPS" "1"

echo "Orchestration tool-loop enabled in ${ENV_FILE}"
echo "Restart Termit API to apply: ./scripts/restart_server.sh"
