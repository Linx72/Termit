#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
echo "== Python tests =="
"${PYTHON_BIN}" -m unittest discover -s tests -q

echo "== Platform e2e =="
if "${PYTHON_BIN}" -c "import fastapi" >/dev/null 2>&1; then
  "${PYTHON_BIN}" -m unittest tests.test_platform_e2e -q
else
  echo "Skip platform e2e: fastapi is not installed in active environment."
fi

echo "== Smoke HTTP =="
if curl -sf --max-time 2 "$BASE_URL/health" >/dev/null 2>&1; then
  ./scripts/smoke_http.sh
echo "== Cursor parity eval gate =="
  curl -sf -X POST "$BASE_URL/api/eval/run-suite" \
    -H 'Content-Type: application/json' \
  -d '{"category":"cursor_parity","limit":20,"persist_report":false}' \
    | TERMIT_EVAL_MIN_PASS_RATE="${TERMIT_EVAL_MIN_PASS_RATE:-0.95}" "${PYTHON_BIN}" scripts/eval_ci_gate.py
elif [[ "${TERMIT_SMOKE_REQUIRE_SERVER:-}" == "1" ]]; then
  echo "TERMIT_SMOKE_REQUIRE_SERVER=1 but server not reachable at $BASE_URL" >&2
  exit 1
else
  echo "Server not running on $BASE_URL — skip live HTTP smoke (run uvicorn on :8765 first)."
fi

if curl -sf --max-time 2 "$BASE_URL/health" >/dev/null 2>&1; then
  echo "== Full eval CI gate =="
  curl -sf -X POST "$BASE_URL/api/eval/run-suite" \
    -H 'Content-Type: application/json' \
    -d '{"persist_report":false}' \
    | "${PYTHON_BIN}" scripts/eval_ci_gate.py
fi
