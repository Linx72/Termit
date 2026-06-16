#!/usr/bin/env bash
# Weekly training loop with eval regression + optional baseline promote.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${TERMIT_STAGE1_ENV_FILE:-${ROOT}/deploy/schedulers/stage1-weekly.env}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

export TERMIT_EVAL_AUTO_PROMOTE_BASELINE="${TERMIT_EVAL_AUTO_PROMOTE_BASELINE:-true}"
export TERMIT_WEEKLY_TRAINING_LOOP="${TERMIT_WEEKLY_TRAINING_LOOP:-true}"

exec "${ROOT}/scripts/training_loop_full.sh"
