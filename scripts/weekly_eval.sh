#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
API_KEY="${TERMIT_API_KEY:-dev-key}"

echo "Enqueue eval suite run against $BASE_URL"
curl -sS -X POST "$BASE_URL/api/eval/run-suite" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"async_mode": false, "limit": 24}' | python3 -m json.tool

echo "Export KPI snapshot"
python3 "$ROOT/scripts/export_kpi_snapshot.py" || true

echo "Done — compare with previous weekly run in data/metrics/"
