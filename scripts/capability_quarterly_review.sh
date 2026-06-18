#!/usr/bin/env bash
# Quarterly capability review: aggregate benchmark history, gate, regression vs baseline.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

LIMIT="${TERMIT_CAP_REVIEW_LIMIT:-12}"
REVIEW_OUT="${TERMIT_CAP_REVIEW_OUT:-/tmp/eval_capability_review.json}"
REGRESSION_OUT="${TERMIT_CAP_REGRESSION_OUT:-/tmp/eval_capability_regression.json}"
BASELINE_PATH="${TERMIT_EVAL_CAPABILITY_BASELINE_PATH:-./data/eval_capability_baseline.json}"
REFRESH_BASELINE="${TERMIT_CAP_REFRESH_BASELINE:-0}"
GATE_TIER="${TERMIT_CAP_GATE_TIER:-}"

if [[ -n "${GATE_TIER}" ]]; then
  echo "== Capability gate tier: ${GATE_TIER} =="
fi

echo "== Capability review (limit=${LIMIT}) =="
"${PYTHON_BIN}" scripts/benchmark_baselines.py \
  --capability-review \
  --capability-limit "${LIMIT}" \
  | tee "${REVIEW_OUT}"

echo "== Capability absolute gate =="
cat "${REVIEW_OUT}" | "${PYTHON_BIN}" scripts/eval_capability_gate.py

echo "== Capability regression gate =="
"${PYTHON_BIN}" scripts/eval_capability_regression_report.py \
  --baseline "${BASELINE_PATH}" \
  --current "${REVIEW_OUT}" \
  --max-pass-gap-drop "${TERMIT_CAP_REG_MAX_PASS_GAP_DROP:-0.05}" \
  --max-quality-gap-drop "${TERMIT_CAP_REG_MAX_QUALITY_GAP_DROP:-0.05}" \
  --max-win-rate-drop "${TERMIT_CAP_REG_MAX_WIN_RATE_DROP:-0.10}" \
  --output "${REGRESSION_OUT}"

if [[ "${REFRESH_BASELINE}" == "1" || "${REFRESH_BASELINE}" == "true" || "${REFRESH_BASELINE}" == "yes" ]]; then
  echo "== Refresh capability baseline (${BASELINE_PATH}) =="
  "${PYTHON_BIN}" scripts/benchmark_baselines.py \
    --refresh-capability-baseline \
    --capability-limit "${LIMIT}" \
    --capability-baseline-out "${BASELINE_PATH}"
fi

echo "Capability quarterly review passed."
