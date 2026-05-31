#!/usr/bin/env bash
# Enqueue weekly Stage1 pipeline via Termit API (wrapper around scripts/stage1_enqueue.py).
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

exec "${PYTHON}" "${ROOT}/scripts/stage1_enqueue.py" --from-env "$@"
