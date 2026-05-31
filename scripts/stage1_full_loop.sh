#!/usr/bin/env bash
# Full continuous-learning loop: enqueue Stage1 -> wait -> train -> optional eval.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${TERMIT_STAGE1_ENV_FILE:-${ROOT}/deploy/schedulers/stage1-weekly.env}"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
fi

echo "[stage1_full_loop] enqueue..."
ENQUEUE_JSON="$("${ROOT}/scripts/stage1_weekly.sh")"
RUN_ID="$(echo "${ENQUEUE_JSON}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
echo "[stage1_full_loop] run_id=${RUN_ID}"

POST_ARGS=(--wait --poll-seconds 5 --timeout-seconds "${TERMIT_FINETUNE_TRAIN_TIMEOUT_SECONDS:-3600}")
if [[ "${TERMIT_FINETUNE_AUTO_REGISTER_AFTER_TRAIN:-false}" == "true" ]]; then
  POST_ARGS+=(--auto-register-adapter)
fi
if [[ "${TERMIT_STAGE1_RUN_POST_EVAL:-true}" == "true" ]]; then
  POST_ARGS+=(--run-post-eval)
fi

exec "${ROOT}/scripts/post_stage1_train.sh" "${RUN_ID}" "${POST_ARGS[@]}"
