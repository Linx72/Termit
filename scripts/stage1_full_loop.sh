#!/usr/bin/env bash
# Full continuous-learning loop: enqueue Stage1 -> wait -> train -> optional eval -> KPI gate.
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

"${ROOT}/scripts/post_stage1_train.sh" "${RUN_ID}" "${POST_ARGS[@]}"
POST_RC=$?
if [[ "$POST_RC" -ne 0 ]]; then
  exit "$POST_RC"
fi

EVAL_REPORT="${ROOT}/data/reports/stage1_post_eval_${RUN_ID}.json"
KPI_BASELINE="${TERMIT_EVAL_KPI_BASELINE:-${ROOT}/data/eval_kpi_baseline.json}"
BASELINE="${TERMIT_EVAL_BASELINE:-${ROOT}/data/eval_baseline_release.json}"
MIN_IMPROVE="${TERMIT_FINETUNE_MIN_EVAL_IMPROVEMENT:-0.05}"

if [[ -f "${EVAL_REPORT}" ]]; then
  echo "[stage1_full_loop] eval KPI gate (min improvement ${MIN_IMPROVE})..."
  KPI_ARGS=(--current "${EVAL_REPORT}" --min-improvement "${MIN_IMPROVE}")
  if [[ -f "${KPI_BASELINE}" ]]; then
    KPI_ARGS=(--baseline "${KPI_BASELINE}" "${KPI_ARGS[@]}")
  elif [[ -f "${BASELINE}" ]]; then
    KPI_ARGS=(--baseline "${BASELINE}" "${KPI_ARGS[@]}")
  fi
  if [[ "${TERMIT_FINETUNE_KPI_STRICT:-false}" == "true" ]]; then
    KPI_ARGS+=(--strict)
  fi
  KPI_OUT="${TERMIT_EVAL_KPI_LAST:-${ROOT}/data/eval_kpi_last.json}"
  KPI_ARGS+=(--output "${KPI_OUT}")
  "${ROOT}/.venv/bin/python" "${ROOT}/scripts/finetune_eval_kpi_gate.py" "${KPI_ARGS[@]}" || exit $?
fi

echo "[stage1_full_loop] complete run_id=${RUN_ID}"
