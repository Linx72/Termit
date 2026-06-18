#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
API_KEY="${TERMIT_API_KEY:-}"

./scripts/smoke_http_core.sh

check_ext() {
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

echo "== Smoke HTTP (extended) =="
check_ext /api/retrieval/repo-map
check_ext /api/projects/agent-templates
check_ext /api/dev/cross-platform/stacks
check_ext /api/finetune/training/dashboard
check_ext /api/desktop/journeys
check_ext /api/desktop/kpi-gates
check_ext /api/desktop/policy-presets
check_ext /api/ops/automation
check_ext /api/ops/plan-status

if [[ -n "$API_KEY" ]]; then
  code="$(curl -s --max-time 30 -o /dev/null -w '%{http_code}' -X POST -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' -d '{"event_type":"smoke_ping","journey_id":"local_feature"}' "$BASE_URL/api/desktop/workflow-events")"
else
  code="$(curl -s --max-time 30 -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{"event_type":"smoke_ping","journey_id":"local_feature"}' "$BASE_URL/api/desktop/workflow-events")"
fi
echo "POST /api/desktop/workflow-events -> HTTP $code"
[[ "$code" == "200" ]]

echo "OK"
