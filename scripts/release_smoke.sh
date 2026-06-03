#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"

cd "$ROOT"
echo "== Python tests =="
python3 -m unittest discover -s tests -q

echo "== Platform e2e =="
python3 -m unittest tests.test_platform_e2e -q

echo "== Smoke HTTP =="
if curl -sf --max-time 2 "$BASE_URL/health" >/dev/null 2>&1; then
  ./scripts/smoke_http.sh
  echo "== Eval CI gate =="
  curl -sf -X POST "$BASE_URL/api/eval/run-suite" \
    -H 'Content-Type: application/json' \
    -d '{"limit":53,"persist_report":false}' \
    | TERMIT_EVAL_MIN_PASS_RATE="${TERMIT_EVAL_MIN_PASS_RATE:-0.95}" python3 scripts/eval_ci_gate.py
elif [[ "${TERMIT_SMOKE_REQUIRE_SERVER:-}" == "1" ]]; then
  echo "TERMIT_SMOKE_REQUIRE_SERVER=1 but server not reachable at $BASE_URL" >&2
  exit 1
else
  echo "Server not running on $BASE_URL — skip live HTTP smoke (run uvicorn on :8765 first)."
fi

if curl -sf --max-time 2 "$BASE_URL/health" >/dev/null 2>&1; then
  echo "== Eval CI gate =="
  curl -sf -X POST "$BASE_URL/api/eval/run-suite" \
    -H 'Content-Type: application/json' \
    -d '{"persist_report":false}' \
    | python3 scripts/eval_ci_gate.py
fi
