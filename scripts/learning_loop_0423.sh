#!/usr/bin/env bash
# Learning loop 0.4.23: pre-DPO baseline → GPU/remote DPO → post-eval HE/MBPP → KPI + cloud benchmark.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate" 2>/dev/null || true

MODEL_RAW="${TERMIT_FINETUNE_OUTPUT_MODEL:-termit-core-ft}"
MODEL="${MODEL_RAW#ollama:}"
SCENARIO_IDS="${TERMIT_EVAL_POST_DPO_IDS:-}"
if [[ -z "${SCENARIO_IDS}" ]]; then
  if [[ "${TERMIT_EVAL_POST_DPO_FULL:-true}" == "true" ]]; then
    if [[ "${TERMIT_LEARNING_LOOP_SKIP_MODEL_BENCHMARK:-false}" == "true" ]]; then
      SCENARIO_IDS="HE1,HE2,MBPP1,MBPP2"
    else
      SCENARIO_IDS="MB1,MB2,MB3,HE1,HE2,MBPP1,MBPP2"
    fi
  else
    SCENARIO_IDS="${TERMIT_EVAL_MODEL_KPI_IDS:-MB1,MB2,MB3}"
  fi
fi

BASELINE="${TERMIT_EVAL_KPI_BASELINE:-${ROOT}/data/eval_kpi_baseline_dpo.json}"
POST_DPO="${TERMIT_EVAL_POST_DPO_REPORT:-${ROOT}/data/eval_post_dpo_last.json}"
KPI_OUT="${TERMIT_EVAL_KPI_LAST:-${ROOT}/data/eval_kpi_last.json}"
ARTIFACT="${TERMIT_LEARNING_LOOP_0423_ARTIFACT:-${ROOT}/data/learning_loop_0423_last.json}"
KPI_MIN="${TERMIT_FINETUNE_MIN_EVAL_IMPROVEMENT:-0.05}"
DPO_JSON_FILE="${TERMIT_DPO_TRAIN_RESULT_JSON:-/tmp/termit_dpo_train_result.json}"
CLOUD_RAN=false
REMOTE_GPU=false

echo "== Learning loop 0.4.23 (model=ollama:${MODEL}, scenarios=${SCENARIO_IDS}) =="

if [[ "${TERMIT_DPO_GPU_REQUIRED:-false}" == "true" || "${TERMIT_LEARNING_LOOP_PREFLIGHT:-false}" == "true" ]]; then
  echo ""
  echo "== 0/6 GPU/cloud preflight =="
  if ! "${ROOT}/scripts/gpu_dpo_preflight.sh"; then
    if [[ "${TERMIT_DPO_GPU_REQUIRED:-false}" == "true" ]]; then
      exit 1
    fi
    echo "WARN: preflight не пройден (non-required)." >&2
  fi
fi

echo ""
echo "== 1/6 Infra probes (GPU + cloud) =="
GPU_JSON="$("${PYTHON_BIN}" "${ROOT}/scripts/gpu_probe.py")"
CLOUD_JSON="$("${PYTHON_BIN}" "${ROOT}/scripts/cloud_benchmark_probe.py")"
echo "GPU: ${GPU_JSON}"
echo "Cloud: ${CLOUD_JSON}"

echo ""
echo "== 2/6 Pre-DPO baseline eval =="
"${PYTHON_BIN}" "${ROOT}/scripts/post_train_model_eval.py" \
  --model "ollama:${MODEL}" \
  --scenario-ids "${SCENARIO_IDS}" \
  --output "${BASELINE}" \
  --persist-report

echo ""
echo "== 3/6 DPO train (local GPU или remote SSH) =="
DPO_EXIT=0
if [[ -n "${TERMIT_REMOTE_GPU_SSH:-}" ]]; then
  REMOTE_GPU=true
  if "${ROOT}/scripts/remote_gpu_dpo.sh"; then
    DPO_EXIT=0
  else
    DPO_EXIT=$?
    echo "WARN: remote DPO train failed (exit ${DPO_EXIT})." >&2
  fi
else
  if "${ROOT}/scripts/dpo_gpu_train.sh"; then
    DPO_EXIT=0
  else
    DPO_EXIT=$?
    echo "WARN: local DPO train failed (exit ${DPO_EXIT})." >&2
  fi
fi

if [[ "${TERMIT_DPO_GPU_REQUIRED:-false}" == "true" && "${DPO_EXIT}" -ne 0 ]]; then
  echo "TERMIT_DPO_GPU_REQUIRED=true — DPO train обязателен, выход ${DPO_EXIT}." >&2
  exit "${DPO_EXIT}"
fi

echo ""
echo "== 4/6 Post-DPO eval (HE1/HE2/MBPP + MB1–MB3) =="
"${PYTHON_BIN}" "${ROOT}/scripts/post_train_model_eval.py" \
  --model "ollama:${MODEL}" \
  --scenario-ids "${SCENARIO_IDS}" \
  --output "${POST_DPO}" \
  --persist-report

echo ""
echo "== 5/6 Finetune eval KPI gate (+${KPI_MIN}) =="
KPI_ARGS=(
  --baseline "${BASELINE}"
  --current "${POST_DPO}"
  --min-improvement "${KPI_MIN}"
  --output "${KPI_OUT}"
)
if [[ "${TERMIT_FINETUNE_KPI_STRICT:-false}" == "true" ]]; then
  KPI_ARGS+=(--strict)
fi
if ! "${PYTHON_BIN}" "${ROOT}/scripts/finetune_eval_kpi_gate.py" "${KPI_ARGS[@]}"; then
  if [[ "${TERMIT_FINETUNE_KPI_STRICT:-false}" == "true" ]]; then
    echo "Finetune KPI strict gate не пройден." >&2
    exit 1
  fi
  echo "WARN: KPI gate не пройден (non-strict)."
fi

echo ""
echo "== 6/6 Cloud benchmark (probe-gated) =="
CLOUD_READY="$(
  echo "${CLOUD_JSON}" | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin).get('ready', False))"
)"
if [[ "${CLOUD_READY}" == "True" || "${CLOUD_READY}" == "true" ]]; then
  if TERMIT_RUN_CLOUD_BENCHMARK=true \
    TERMIT_CAP_GATE_TIER="${TERMIT_CAP_GATE_TIER:-release}" \
    "${ROOT}/scripts/cloud_benchmark_cycle.sh"; then
    CLOUD_RAN=true
  else
    if [[ "${TERMIT_CLOUD_BENCHMARK_REQUIRED:-false}" == "true" ]]; then
      echo "Cloud benchmark required but failed." >&2
      exit 1
    fi
    echo "WARN: cloud benchmark cycle failed (non-blocking)."
  fi
else
  echo "Cloud probe not ready — skip benchmark run."
  if [[ "${TERMIT_CLOUD_BENCHMARK_REQUIRED:-false}" == "true" ]]; then
    echo "TERMIT_CLOUD_BENCHMARK_REQUIRED=true — cloud benchmark обязателен." >&2
    exit 1
  fi
fi

DPO_JSON_CONTENT=""
if [[ -f "${DPO_JSON_FILE}" ]]; then
  DPO_JSON_CONTENT="$(cat "${DPO_JSON_FILE}")"
fi

REPORT_ARGS=(
  --gpu-json "${GPU_JSON}"
  --cloud-json "${CLOUD_JSON}"
  --baseline "${BASELINE}"
  --post-dpo "${POST_DPO}"
  --kpi "${KPI_OUT}"
  --model "ollama:${MODEL}"
  --scenario-ids "${SCENARIO_IDS}"
  --output "${ARTIFACT}"
)
if [[ "${CLOUD_RAN}" == "true" ]]; then
  REPORT_ARGS+=(--cloud-ran)
fi
if [[ "${REMOTE_GPU}" == "true" ]]; then
  REPORT_ARGS+=(--remote-gpu)
fi
if [[ -n "${DPO_JSON_CONTENT}" ]]; then
  REPORT_ARGS+=(--dpo-json "${DPO_JSON_CONTENT}")
fi

echo ""
echo "== Artifact learning_loop_0423 =="
"${PYTHON_BIN}" "${ROOT}/scripts/learning_loop_0423_report.py" "${REPORT_ARGS[@]}"

echo ""
echo "OK — learning loop 0.4.23 complete."
echo "  Baseline: ${BASELINE}"
echo "  Post-DPO: ${POST_DPO}"
echo "  KPI:      ${KPI_OUT}"
echo "  Artifact: ${ARTIFACT}"
