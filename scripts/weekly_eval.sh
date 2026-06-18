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

echo "Capability quarterly review (benchmark history gates)"
if curl -sf --max-time 5 "$BASE_URL/health" >/dev/null 2>&1; then
  # Weekly loop uses CI tier; release tier is for quarterly_capability.sh / pre-release.
  TERMIT_CAP_GATE_TIER="${TERMIT_CAP_GATE_TIER:-ci}" \
  TERMIT_CAP_REVIEW_LIMIT="${TERMIT_CAP_REVIEW_LIMIT:-12}" \
    TERMIT_EVAL_CAPABILITY_BASELINE_PATH="${TERMIT_EVAL_CAPABILITY_BASELINE_PATH:-$ROOT/data/eval_capability_baseline.json}" \
    TERMIT_CAP_REFRESH_BASELINE="${TERMIT_CAP_REFRESH_BASELINE:-0}" \
    "$ROOT/scripts/capability_quarterly_review.sh"
  if [[ "${TERMIT_CAP_REFRESH_BASELINE:-0}" == "1" || "${TERMIT_CAP_REFRESH_BASELINE:-0}" == "true" ]]; then
    echo "Refreshing capability baseline"
    TERMIT_EVAL_CAPABILITY_BASELINE_PATH="${TERMIT_EVAL_CAPABILITY_BASELINE_PATH:-$ROOT/data/eval_capability_baseline.json}" \
      "$ROOT/scripts/capability_baseline_refresh.sh"
  fi
else
  echo "Skip capability review: server unreachable at $BASE_URL"
fi

echo "Done — compare with previous weekly run in data/metrics/"
