#!/usr/bin/env bash
# Wait for Stage1 run, train Ollama model, optional post-eval.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${TERMIT_STAGE1_ENV_FILE:-${ROOT}/deploy/schedulers/stage1-weekly.env}"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
fi

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="python3"
fi

exec "${PYTHON}" "${ROOT}/scripts/post_stage1_train.py" "$@"
