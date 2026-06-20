#!/usr/bin/env bash
# End-to-end verification bundle for Termit roadmap gates (local-safe defaults).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate" 2>/dev/null || true

echo "== Termit do-all verify =="

if [[ "${TERMIT_DO_ALL_CI:-false}" != "true" ]]; then
  echo "== 1/8 Unit tests (eval + orch + finetune slice) =="
  "${PYTHON_BIN}" -m unittest \
    tests.test_eval_orchestration_spike \
    tests.test_eval_orchestration_gate_tiers \
    tests.test_multi_agent_orchestrator \
    tests.test_model_bound_eval_gate \
    tests.test_finetune_training_dashboard \
    tests.test_gpu_and_automation_scripts \
    tests.test_weekly_closed_loop \
    -q
else
  echo "== 1/8 Unit tests =="
  echo "Skip (TERMIT_DO_ALL_CI=true — already ran in CI job)."
fi

DPO_DATASET="${TERMIT_DPO_DATASET:-}"
if [[ "${TERMIT_DO_ALL_SKIP_DPO:-false}" == "true" ]]; then
  echo ""
  echo "Skip DPO export/contract (TERMIT_DO_ALL_SKIP_DPO=true)."
elif [[ -n "${DPO_DATASET}" && -f "${DPO_DATASET}" ]]; then
  echo ""
  echo "== 2/8 DPO contract gate (existing dataset) =="
  "${PYTHON_BIN}" "${ROOT}/scripts/eval_dpo_contract_gate.py" \
    --dataset "${DPO_DATASET}" \
    --min-rows "${TERMIT_DPO_CONTRACT_MIN_ROWS:-1}"
else
  echo ""
  echo "== 2/8 DPO export + contract gate =="
  "${ROOT}/scripts/do_all_dpo_contract.sh"
fi

if [[ "${TERMIT_DO_ALL_SKIP_MODEL_BOUND:-false}" != "true" ]]; then
  echo ""
  echo "== 2b/8 Model-bound CI gate (offline fixtures) =="
  TERMIT_MODEL_BOUND_GATE_TIER=model_bound_ci \
    "${PYTHON_BIN}" "${ROOT}/scripts/model_bound_eval_gate.py"
fi

if [[ "${TERMIT_DO_ALL_SKIP_SWE:-false}" != "true" ]]; then
  echo ""
  echo "== 2c/8 SWE bench slice (offline fixtures) =="
  "${PYTHON_BIN}" "${ROOT}/scripts/swe_eval_gate.py"
fi

if [[ "${TERMIT_DO_ALL_TRY_DPO_TRAIN:-false}" == "true" ]]; then
  echo ""
  echo "== 3/8 DPO dry train (GPU probe) =="
  "${ROOT}/scripts/dpo_gpu_train.sh"
fi

if curl -sf --max-time 5 "${BASE_URL}/health" >/dev/null 2>&1; then
  echo ""
  echo "== 4/8 HTTP smoke =="
  ./scripts/smoke_http_core.sh

  echo ""
  echo "== 5/8 DPO status =="
  curl -sf "${BASE_URL}/api/finetune/dpo/status" | "${PYTHON_BIN}" -m json.tool | head -12

  echo ""
  echo "== 6/8 Local orchestration gate (fixture) =="
  if [[ "${TERMIT_DO_ALL_CI:-false}" == "true" ]]; then
    export TERMIT_ORCH_SKIP_SERVER_RESTART=true
  fi
  TERMIT_ORCH_SPIKE_USE_FIXTURE=true "${ROOT}/scripts/run_local_orchestration_gate.sh"

  echo ""
  echo "== 7/8 Cloud benchmark cycle (gates-only) =="
  TERMIT_RUN_CLOUD_BENCHMARK=false TERMIT_CAP_GATE_TIER=ci ./scripts/cloud_benchmark_cycle.sh

  if [[ "${TERMIT_DO_ALL_TRY_LIVE_ORCH:-false}" == "true" ]]; then
    echo ""
    echo "== 8/8 Live orchestration gate (no fixture) =="
    ./scripts/run_live_orchestration_gate.sh
  else
    echo ""
    echo "Skip live orchestration gate (set TERMIT_DO_ALL_TRY_LIVE_ORCH=true to enable)."
  fi

  if [[ "${TERMIT_DO_ALL_TRY_STRICT_LIVE_ORCH:-false}" == "true" ]]; then
    echo ""
    echo "== 8b/8 Strict live orchestration gate (no fallback) =="
    ./scripts/run_strict_live_orchestration_gate.sh
  fi

  if [[ "${TERMIT_DO_ALL_CAPTURE_KPI_BASELINE:-false}" == "true" ]]; then
    echo ""
    echo "== KPI baseline capture =="
    ./scripts/capture_eval_kpi_baseline.sh
  fi

  if [[ "${TERMIT_DO_ALL_TRY_CLOUD:-false}" == "true" ]]; then
    echo ""
    echo "== 9/9 Cloud benchmark cycle (probe-gated) =="
    TERMIT_RUN_CLOUD_BENCHMARK=true TERMIT_CAP_GATE_TIER="${TERMIT_CAP_GATE_TIER:-release}" \
      ./scripts/cloud_benchmark_cycle.sh
  elif [[ -n "${OPENAI_COMPAT_API_KEY:-}" || -n "${OPENAI_API_KEY:-}" ]]; then
    echo ""
    echo "== 9/9 Cloud benchmark cycle (auto: API key в env) =="
    TERMIT_RUN_CLOUD_BENCHMARK=true TERMIT_CAP_GATE_TIER="${TERMIT_CAP_GATE_TIER:-ci}" \
      ./scripts/cloud_benchmark_cycle.sh || echo "WARN: cloud benchmark failed (non-blocking)."
  fi
else
  echo "Server not reachable at ${BASE_URL} — skip HTTP/gate steps."
  echo "Start: ./scripts/restart_server.sh"
fi

echo ""
"${ROOT}/scripts/reset_eval_patch_fixture.sh" || true

echo ""
echo "OK — do-all verify complete."
