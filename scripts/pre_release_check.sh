#!/usr/bin/env bash
# Pre-release checklist: local release gate + optional staging gate (без git push).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"

PROFILE="${TERMIT_RELEASE_SMOKE_PROFILE:-extended}"
RUN_STAGING="${TERMIT_RELEASE_RUN_STAGING:-auto}"
STRICT_PLAN="${TERMIT_RELEASE_PLAN_STRICT:-false}"

echo "== Termit pre-release check (profile=${PROFILE}, staging=${RUN_STAGING}) =="

STAGING_ARGS=()
if [[ "${RUN_STAGING}" == "true" ]]; then
  STAGING_ARGS+=(true)
elif [[ "${RUN_STAGING}" == "auto" ]]; then
  if docker info >/dev/null 2>&1 && curl -sf --max-time 3 "${TERMIT_HOSTED_BASE_URL:-http://127.0.0.1:8080}/health" >/dev/null 2>&1; then
    STAGING_ARGS+=(true)
    echo "Staging :8080 доступен — включим release_gate_staging."
  else
    STAGING_ARGS+=(false)
    echo "Staging недоступен — только local gate."
  fi
else
  STAGING_ARGS+=(false)
fi

TERMIT_RELEASE_SMOKE_PROFILE="${PROFILE}" \
TERMIT_RELEASE_RUN_STAGING="${STAGING_ARGS[0]}" \
TERMIT_RELEASE_PLAN_STRICT="${STRICT_PLAN}" \
  "${ROOT}/scripts/release_gate_local.sh"

echo ""
echo "OK — pre-release check passed."
echo "  Tag release: ./scripts/release_all.sh (после release_pack + VERSION bump)"
