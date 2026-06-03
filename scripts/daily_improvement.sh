#!/usr/bin/env bash
# Trigger Termit daily self-improvement loop via API.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
API_KEY="${TERMIT_API_KEY:-${TERMIT_DEV_API_KEY:-dev-key}}"

curl -sf -X POST "${BASE_URL}/api/ops/daily-improvement/trigger" \
  -H "X-API-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  | python3 -m json.tool
