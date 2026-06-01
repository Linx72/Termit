#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
API_KEY="${TERMIT_API_KEY:-}"

check() {
  local path="$1"
  local code
  if [[ -n "$API_KEY" ]]; then
    code="$(curl -s --max-time 30 -o /dev/null -w '%{http_code}' -H "X-API-Key: $API_KEY" "$BASE_URL$path")"
  else
    code="$(curl -s --max-time 30 -o /dev/null -w '%{http_code}' "$BASE_URL$path")"
  fi
  echo "$path -> HTTP $code"
  [[ "$code" == "200" ]]
}

echo "== Smoke HTTP =="
check /health
check /healthz
check /api/metrics/thresholds
check /api/ops/readiness
check /api/ops/agent-runs/metrics
check /api/retrieval/repo-map
check /api/projects/agent-templates
check /api/finetune/training/dashboard
check /api/eval/dashboard

echo "OK"
