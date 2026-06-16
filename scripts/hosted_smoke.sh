#!/usr/bin/env bash
# Hosted beta smoke — checks Termit through Caddy reverse proxy (:8080 default).
#
# Usage:
#   docker compose up --build -d
#   ./scripts/hosted_smoke.sh
#
# With auth (deploy/docker.env.example):
#   TERMIT_API_KEY=viewer-key TERMIT_HOSTED_AUTH_EXPECT=true ./scripts/hosted_smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_HOSTED_BASE_URL:-http://127.0.0.1:8080}"
API_KEY="${TERMIT_API_KEY:-${TERMIT_HOSTED_API_KEY:-}}"
AUTH_EXPECT="${TERMIT_HOSTED_AUTH_EXPECT:-false}"
TIMEOUT="${TERMIT_HOSTED_SMOKE_TIMEOUT:-30}"

cd "$ROOT"

curl_code() {
  local path="$1"
  shift || true
  if [[ -n "$API_KEY" ]]; then
    if [[ $# -gt 0 ]]; then
      curl -s --max-time "$TIMEOUT" -o /dev/null -w '%{http_code}' \
        -H "X-API-Key: ${API_KEY}" "$@" "${BASE_URL}${path}"
    else
      curl -s --max-time "$TIMEOUT" -o /dev/null -w '%{http_code}' \
        -H "X-API-Key: ${API_KEY}" "${BASE_URL}${path}"
    fi
  else
    if [[ $# -gt 0 ]]; then
      curl -s --max-time "$TIMEOUT" -o /dev/null -w '%{http_code}' \
        "$@" "${BASE_URL}${path}"
    else
      curl -s --max-time "$TIMEOUT" -o /dev/null -w '%{http_code}' \
        "${BASE_URL}${path}"
    fi
  fi
}

curl_headers() {
  local path="$1"
  if [[ -n "$API_KEY" ]]; then
    curl -s --max-time "$TIMEOUT" -D - -o /dev/null -H "X-API-Key: ${API_KEY}" "${BASE_URL}${path}"
  else
    curl -s --max-time "$TIMEOUT" -D - -o /dev/null "${BASE_URL}${path}"
  fi
}

expect_code() {
  local path="$1"
  local want="$2"
  shift 2
  local got
  got="$(curl_code "$path" "$@")"
  echo "${path} -> HTTP ${got} (want ${want})"
  [[ "$got" == "$want" ]]
}

echo "== Termit hosted smoke =="
echo "Base URL: ${BASE_URL}"

if ! curl -s --max-time 3 -o /dev/null "${BASE_URL}/health" 2>/dev/null; then
  echo "Hosted proxy not reachable at ${BASE_URL}" >&2
  echo "Start stack: docker compose up --build -d" >&2
  exit 1
fi

echo ""
echo "== 1/5 Public health via proxy =="
expect_code /health 200
expect_code /healthz 200

echo ""
echo "== 2/5 Ops + metrics =="
expect_code /api/metrics/thresholds 200
expect_code /api/ops/readiness 200
expect_code /api/eval/dashboard 200
expect_code /api/desktop/kpi-gates 200
expect_code /api/ops/beta-metrics 200

if [[ -n "$API_KEY" ]]; then
  expect_code /api/ops/agent-runs/metrics 200
else
  metrics_code="$(curl_code /api/ops/agent-runs/metrics)"
  echo "/api/ops/agent-runs/metrics -> HTTP ${metrics_code}"
  if [[ "$metrics_code" != "200" && "$metrics_code" != "401" && "$metrics_code" != "403" ]]; then
    echo "Unexpected metrics status: ${metrics_code}" >&2
    exit 1
  fi
fi

echo ""
echo "== 3/5 Trace header =="
headers="$(curl_headers /health)"
if echo "$headers" | grep -qi '^x-trace-id:'; then
  echo "X-Trace-Id present on /health"
else
  echo "Missing X-Trace-Id header on /health" >&2
  exit 1
fi

echo ""
echo "== 4/5 Auth policy (optional) =="
if [[ "$AUTH_EXPECT" == "true" ]]; then
  if [[ -z "$API_KEY" ]]; then
    echo "TERMIT_HOSTED_AUTH_EXPECT=true requires TERMIT_API_KEY" >&2
    exit 1
  fi
  unauth_code="$(curl -s --max-time "$TIMEOUT" -o /dev/null -w '%{http_code}' "${BASE_URL}/api/ops/agent-runs/metrics")"
  echo "/api/ops/agent-runs/metrics (no key) -> HTTP ${unauth_code}"
  if [[ "$unauth_code" != "401" && "$unauth_code" != "403" ]]; then
    echo "Expected 401/403 without API key when auth enabled" >&2
    exit 1
  fi
  expect_code /api/ops/agent-runs/metrics 200
else
  echo "Skip auth gate (set TERMIT_HOSTED_AUTH_EXPECT=true to enforce)"
fi

echo ""
echo "== 5/5 Media Studio (optional) =="
MEDIA_EXPECT="${TERMIT_HOSTED_MEDIA_EXPECT:-false}"
if [[ "$MEDIA_EXPECT" == "true" ]]; then
  media_body='{"prompt":"hosted smoke icon","width":64,"height":64,"project_id":"hosted-smoke","provider":"stub"}'
  if [[ -n "$API_KEY" ]]; then
    media_code="$(curl -s --max-time "$TIMEOUT" -o /tmp/termit_media_smoke.json -w '%{http_code}' \
      -H "Content-Type: application/json" -H "X-API-Key: ${API_KEY}" \
      -d "$media_body" "${BASE_URL}/api/media/generate-image")"
  else
    media_code="$(curl -s --max-time "$TIMEOUT" -o /tmp/termit_media_smoke.json -w '%{http_code}' \
      -H "Content-Type: application/json" \
      -d "$media_body" "${BASE_URL}/api/media/generate-image")"
  fi
  echo "/api/media/generate-image -> HTTP ${media_code}"
  if [[ "$media_code" != "200" ]]; then
    echo "Media smoke failed (set TERMIT_MEDIA_ENABLED=true in docker env)" >&2
    exit 1
  fi
  asset_id="$(python3 -c "import json; print(json.load(open('/tmp/termit_media_smoke.json'))['asset']['asset_id'])" 2>/dev/null || true)"
  if [[ -z "$asset_id" ]]; then
    echo "Media response missing asset_id" >&2
    exit 1
  fi
  expect_code "/api/media/assets/${asset_id}/file" 200
  echo "Media asset file download OK"
else
  echo "Skip media gate (set TERMIT_HOSTED_MEDIA_EXPECT=true to enforce)"
fi

echo ""
echo "OK — hosted smoke passed via ${BASE_URL}"
