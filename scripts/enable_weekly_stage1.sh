#!/usr/bin/env bash
# Enable weekly Stage1 closed loop with auto-train and shadow traffic.
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
    sed -i '' "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
  else
    echo "${key}=${value}" >> "${ENV_FILE}"
  fi
}

set_env "TERMIT_STAGE1_SCHEDULE_ENABLED" "true"
set_env "TERMIT_FINETUNE_AUTO_TRAIN" "true"
set_env "TERMIT_FINETUNE_AUTO_REGISTER_AFTER_TRAIN" "true"
set_env "TERMIT_STAGE1_SCHEDULE_AUTO_REGISTER_ADAPTER" "true"
set_env "TERMIT_FINETUNE_SHADOW_TRAFFIC_PERCENT" "10"
set_env "TERMIT_CLOUD_TEACHER_MODEL" "openai_compat:deepseek-ai/DeepSeek-V3"
set_env "TERMIT_EVAL_BENCHMARK_REFERENCE_MODEL" "openai_compat:deepseek-ai/DeepSeek-V3"
set_env "TERMIT_FINETUNE_PIPELINE_STUCK_TIMEOUT_SECONDS" "3600"

"${PYTHON}" "${ROOT}/scripts/stage1_recover_and_export.py" --stale-seconds 60

echo "Weekly Stage1 loop enabled in ${ENV_FILE}"
