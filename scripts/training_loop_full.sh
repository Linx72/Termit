#!/usr/bin/env bash
# Full training loop: signals → dataset → job → eval → regression gate → KPI dashboard.
#
# Requires Termit API on :8765 with eval endpoints enabled.
# Usage:
#   ./scripts/training_loop_full.sh
#   TERMIT_EVAL_CATEGORY=cursor_parity TERMIT_EVAL_LIMIT=20 ./scripts/training_loop_full.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
API_KEY="${TERMIT_API_KEY:-}"
BASELINE="${TERMIT_EVAL_BASELINE:-$ROOT/data/eval_baseline_release.json}"
CATEGORY="${TERMIT_EVAL_CATEGORY:-cursor_parity}"
LIMIT="${TERMIT_EVAL_LIMIT:-20}"
MAX_DROP="${TERMIT_EVAL_MAX_PASS_RATE_DROP:-0.05}"
CURRENT_REPORT="/tmp/termit_eval_current_$$.json"

cd "$ROOT"
source .venv/bin/activate 2>/dev/null || true

AUTH=()
if [[ -n "$API_KEY" ]]; then
  AUTH=(-H "X-API-Key: ${API_KEY}")
fi

echo "== Termit training loop (full) =="

echo "== 1/5 Health check =="
for i in $(seq 1 20); do
  if curl -sf --max-time 3 "${AUTH[@]}" "$BASE_URL/health" >/dev/null; then
    break
  fi
  if [[ "$i" -eq 20 ]]; then
    echo "Termit API not reachable at $BASE_URL" >&2
    exit 1
  fi
  sleep 1
done

echo "== 2/5 Export dataset + finetune job (week2) =="
"$ROOT/scripts/training_loop_week2.sh"

echo ""
echo "== 3/5 Eval suite (category=${CATEGORY}, limit=${LIMIT}) =="
curl -sf "${AUTH[@]}" -X POST "$BASE_URL/api/eval/run-suite" \
  -H "Content-Type: application/json" \
  -d "{\"category\":\"${CATEGORY}\",\"limit\":${LIMIT},\"persist_report\":true}" \
  | tee "$CURRENT_REPORT" \
  | python3 -m json.tool | head -40

echo ""
echo "== 4/5 Regression gate vs baseline =="
if [[ ! -f "$BASELINE" ]]; then
  echo "Baseline missing: $BASELINE — skip regression gate." >&2
else
  python3 "$ROOT/scripts/eval_regression_report.py" \
    --baseline "$BASELINE" \
    --current "$CURRENT_REPORT" \
    --max-pass-rate-drop "$MAX_DROP"
fi

echo ""
echo "== 5/5 Training dashboard + agent metrics =="
curl -sf "${AUTH[@]}" "$BASE_URL/api/finetune/training/dashboard?limit=5" | python3 -m json.tool | head -40
echo ""
curl -sf "${AUTH[@]}" "$BASE_URL/api/ops/agent-runs/metrics" | python3 -m json.tool | head -20

echo ""
echo "OK — training loop full complete."
echo "Current eval report: $CURRENT_REPORT"
