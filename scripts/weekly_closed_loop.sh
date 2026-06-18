#!/usr/bin/env bash
# Weekly closed loop: training (optional) → shadow gate → eval → capability review → orchestration slice.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
API_KEY="${TERMIT_API_KEY:-}"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate" 2>/dev/null || true

echo "== Termit weekly closed loop =="

if [[ "${TERMIT_WEEKLY_RUN_TRAINING_LOOP:-false}" == "true" ]]; then
  if curl -sf --max-time 5 "${BASE_URL}/health" >/dev/null 2>&1; then
    echo "== 1/4 Training loop (full) =="
    TERMIT_EVAL_AUTO_PROMOTE_BASELINE="${TERMIT_EVAL_AUTO_PROMOTE_BASELINE:-false}" \
      "${ROOT}/scripts/training_loop_full.sh"
  else
    echo "Skip training loop: server unreachable at ${BASE_URL}"
  fi
else
  echo "Skip training loop: TERMIT_WEEKLY_RUN_TRAINING_LOOP=false"
fi

if curl -sf --max-time 5 "${BASE_URL}/health" >/dev/null 2>&1; then
  echo ""
  echo "== 2/4 Shadow traffic gate =="
  TERMIT_API_KEY="${API_KEY}" "${PYTHON_BIN}" "${ROOT}/scripts/shadow_traffic_gate.py" \
    --base-url "${BASE_URL}"

  echo ""
  echo "== 3/4 Weekly eval + capability review =="
  TERMIT_CAP_GATE_TIER="${TERMIT_CAP_GATE_TIER:-ci}" \
    TERMIT_BASE_URL="${BASE_URL}" TERMIT_API_KEY="${API_KEY}" \
    "${ROOT}/scripts/weekly_eval.sh"

  if [[ "${TERMIT_WEEKLY_RUN_CLOUD_BENCHMARK:-false}" == "true" ]]; then
    echo ""
    echo "== 3b/4 Cloud benchmark cycle =="
    TERMIT_BASE_URL="${BASE_URL}" TERMIT_API_KEY="${API_KEY}" \
      "${ROOT}/scripts/cloud_benchmark_cycle.sh"
  fi

  echo ""
  echo "== 4/4 Orchestration eval slice =="
  ORCH_GATE_TIER="${TERMIT_ORCH_GATE_TIER:-}"
  if [[ -z "${ORCH_GATE_TIER}" ]]; then
    ORCH_GATE_TIER="$(
      TERMIT_BASE_URL="${BASE_URL}" "${PYTHON_BIN}" - <<'PY' 2>/dev/null || echo ci
import json
import os
import urllib.request

base = os.environ.get("TERMIT_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
try:
    with urllib.request.urlopen(f"{base}/api/orchestration/config", timeout=8) as resp:
        print(json.load(resp).get("gate_tier", "ci"))
except Exception:
    print("ci")
PY
    )"
  fi
  echo "Orchestration gate tier: ${ORCH_GATE_TIER}"
  ORCH_ARGS=(
    --base-url "${BASE_URL}"
    --prompts-file "${ROOT}/data/eval_scenarios_orchestration.json"
    --max-prompts "${TERMIT_ORCH_SPIKE_MAX_PROMPTS:-3}"
    --timeout-seconds "${TERMIT_ORCH_SPIKE_TIMEOUT_SECONDS:-120}"
    --min-pass-rate "${TERMIT_ORCH_SPIKE_MIN_PASS_RATE:-0.0}"
    --output-file /tmp/orch_eval_report_weekly.json
    --append-report-file "${ROOT}/data/orchestration_eval_reports.jsonl"
  )
  TERMIT_ORCH_REQUIRE_TOOL_LOOP="${TERMIT_ORCH_REQUIRE_TOOL_LOOP:-false}" \
    TERMIT_ORCH_MIN_TOOL_LOOP_STEPS="${TERMIT_ORCH_MIN_TOOL_LOOP_STEPS:-1}" \
    "${PYTHON_BIN}" "${ROOT}/scripts/eval_orchestration_spike.py" "${ORCH_ARGS[@]}"
  TERMIT_ORCH_GATE_TIER="${ORCH_GATE_TIER}" \
    cat /tmp/orch_eval_report_weekly.json | "${PYTHON_BIN}" "${ROOT}/scripts/eval_orchestration_gate.py"
else
  echo "Skip runtime gates: server unreachable at ${BASE_URL}" >&2
  exit 1
fi

echo ""
echo "OK — weekly closed loop complete."
