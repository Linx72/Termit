#!/usr/bin/env bash
# Локальный smoke V4 ladder + eval 3.0 без cloud API key.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"

echo "== V4 ladder smoke (local, no cloud key required) =="

echo ""
echo "== 1/4 Phase 0 readiness =="
TERMIT_PHASE0_STRICT=false TERMIT_PHASE0_RUN_BENCHMARK=false \
  "${ROOT}/scripts/phase0_v4_readiness.sh"

echo ""
echo "== 2/4 Capability benchmark CI =="
"${ROOT}/scripts/capability_benchmark_ci.sh"

echo ""
echo "== 3/4 Model-bound eval gate (CI tier) =="
TERMIT_MODEL_BOUND_GATE_TIER=model_bound_ci \
  "${PYTHON_BIN}" "${ROOT}/scripts/model_bound_eval_gate.py"

echo ""
echo "== 4/4 Learning loop 0.4.23 CI slice =="
"${ROOT}/scripts/learning_loop_0423_ci.sh"

echo ""
echo "OK — V4 ladder smoke complete."
