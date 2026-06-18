#!/usr/bin/env bash
# Снимок plan status в data/plan_status_last.json (через API).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
OUT="${TERMIT_PLAN_STATUS_SNAPSHOT:-$ROOT/data/plan_status_last.json}"
API_KEY="${TERMIT_API_KEY:-}"

cd "$ROOT"
mkdir -p "$(dirname "$OUT")"

CURL_ARGS=(-sS --max-time 30 "$BASE_URL/api/ops/plan-status")
if [[ -n "$API_KEY" ]]; then
  CURL_ARGS=(-sS --max-time 30 -H "X-API-Key: $API_KEY" "$BASE_URL/api/ops/plan-status")
fi

curl "${CURL_ARGS[@]}" | "${ROOT}/.venv/bin/python" -m json.tool > "$OUT"
echo "OK — plan status snapshot: $OUT"
