#!/usr/bin/env bash
# Preflight для real DPO / learning loop 0.4.23: GPU, remote SSH, cloud key.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

# Без source .env — в файле могут быть значения, ломающие bash.
read_dotenv_key() {
  local key="$1"
  local file="${ROOT}/.env"
  [[ -f "$file" ]] || return 0
  grep -E "^${key}=" "$file" 2>/dev/null | tail -1 | cut -d= -f2- | sed -E 's/^["'\'' ]+|["'\'' ]+$//g' || true
}

if [[ -z "${TERMIT_REMOTE_GPU_SSH:-}" ]]; then
  _remote="$(read_dotenv_key TERMIT_REMOTE_GPU_SSH)"
  if [[ -n "${_remote}" ]]; then
    TERMIT_REMOTE_GPU_SSH="${_remote}"
  fi
fi

echo "== GPU / DPO preflight (0.4.23) =="

GPU_JSON="$("${PYTHON_BIN}" "${ROOT}/scripts/gpu_probe.py")"
CLOUD_JSON="$("${PYTHON_BIN}" "${ROOT}/scripts/cloud_benchmark_probe.py")"
echo "GPU:  ${GPU_JSON}"
echo "Cloud: ${CLOUD_JSON}"

GPU_OK="$(echo "${GPU_JSON}" | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin).get('gpu_available', False))")"
CLOUD_OK="$(echo "${CLOUD_JSON}" | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin).get('ready', False))")"
REMOTE="${TERMIT_REMOTE_GPU_SSH:-}"

BLOCKERS=0

if [[ "${GPU_OK}" != "True" && "${GPU_OK}" != "true" ]]; then
  if [[ -z "${REMOTE}" ]]; then
    echo "BLOCKER: нет локального GPU и не задан TERMIT_REMOTE_GPU_SSH (см. .env.example)." >&2
    BLOCKERS=$((BLOCKERS + 1))
  else
    echo "INFO: локального GPU нет; будет remote SSH → ${REMOTE}"
    if ! ssh -o BatchMode=yes -o ConnectTimeout=8 "${REMOTE}" "echo ok" >/dev/null 2>&1; then
      echo "BLOCKER: SSH к ${REMOTE} недоступен (BatchMode)." >&2
      BLOCKERS=$((BLOCKERS + 1))
    else
      echo "OK — SSH probe ${REMOTE}"
    fi
  fi
else
  echo "OK — локальный GPU доступен"
fi

if [[ "${CLOUD_OK}" != "True" && "${CLOUD_OK}" != "true" ]]; then
  echo "WARN: cloud benchmark не готов (OPENAI_COMPAT_API_KEY / OPENAI_API_KEY)." >&2
fi

if [[ "${BLOCKERS}" -gt 0 ]]; then
  echo ""
  echo "Следующие шаги:"
  echo "  1. Self-hosted GPU runner + workflow gpu-dpo-learning-loop.yml (workflow_dispatch)"
  echo "  2. export TERMIT_REMOTE_GPU_SSH=user@gpu-host && ./scripts/remote_gpu_dpo.sh"
  echo "  3. export OPENAI_COMPAT_API_KEY=... для cloud benchmark"
  exit 1
fi

echo ""
echo "OK — preflight passed; запускайте ./scripts/learning_loop_0423.sh"
