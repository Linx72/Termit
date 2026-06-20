#!/usr/bin/env bash
# Фаза 0 readiness: V4 ladder env + cloud probe + optional benchmark (без dev seed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

STRICT="${TERMIT_PHASE0_STRICT:-false}"
FAIL=0

echo "== Termit phase 0 — V4 readiness =="

echo ""
echo "== 1/4 Frontier ladder defaults =="
"${PYTHON_BIN}" -c "
from app.core.config import get_settings
from app.core.frontier_models import frontier_fallback_chain, resolve_benchmark_reference_model
s = get_settings()
print('reference:', resolve_benchmark_reference_model(s))
print('frontier:', s.frontier_fallback_model)
print('chain:', frontier_fallback_chain(s))
"

echo ""
echo "== 2/4 Cloud benchmark probe =="
PROBE_JSON="$("${PYTHON_BIN}" "${ROOT}/scripts/cloud_benchmark_probe.py")"
echo "${PROBE_JSON}"
PROBE_READY="$(
  echo "${PROBE_JSON}" | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin).get('ready', False))"
)"
if [[ "${PROBE_READY}" != "True" && "${PROBE_READY}" != "true" ]]; then
  echo "WARN: cloud benchmark not ready (missing API key or dev stub off)."
  FAIL=1
fi

echo ""
echo "== 3/4 GPU probe =="
if "${PYTHON_BIN}" "${ROOT}/scripts/gpu_probe.py" 2>/dev/null; then
  echo "GPU: ok"
else
  echo "WARN: no GPU — DPO будет dry-run."
  FAIL=1
fi

echo ""
echo "== 4/4 Optional capability run =="
if [[ "${TERMIT_PHASE0_RUN_BENCHMARK:-false}" == "true" ]]; then
  "${ROOT}/scripts/cloud_benchmark_cycle.sh"
else
  echo "SKIP (set TERMIT_PHASE0_RUN_BENCHMARK=true to run cloud_benchmark_cycle.sh)"
fi

if [[ "${STRICT}" == "true" && "${FAIL}" -ne 0 ]]; then
  echo "FAIL — phase 0 strict mode" >&2
  exit 1
fi

echo ""
echo "OK — phase 0 readiness check complete."
