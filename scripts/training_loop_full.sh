#!/usr/bin/env bash
# Полный training loop: signals → dataset → job → eval → regression gate → KPI dashboard.
#
# Требуется Termit API на :8765 с включёнными eval endpoints.
# Примеры:
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
GATE_OK=0

cd "$ROOT"
source .venv/bin/activate 2>/dev/null || true

curl_api() {
  if [[ -n "${API_KEY}" ]]; then
    curl -sf -H "X-API-Key: ${API_KEY}" "$@"
  else
    curl -sf "$@"
  fi
}

echo "== Termit training loop (full) =="

echo "== 1/5 Health check =="
for i in $(seq 1 20); do
  if curl_api --max-time 3 "${BASE_URL}/health" >/dev/null; then
    break
  fi
  if [[ "$i" -eq 20 ]]; then
    echo "Termit API not reachable at $BASE_URL" >&2
    exit 1
  fi
  sleep 1
done

echo "== 1a/5 Normalize training signals =="
python3 "$ROOT/scripts/normalize_training_signals.py" || true

USE_MODEL_KPI=false
if [[ "${TERMIT_FINETUNE_AUTO_TRAIN:-false}" == "true" ]]; then
  USE_MODEL_KPI=true
  echo ""
  echo "== 1b/5 Model KPI baseline (pre-train, MB1-MB3) =="
  PRE_TRAIN_MODEL="${TERMIT_EVAL_PRE_TRAIN_MODEL:-ollama:deepseek-coder}"
  KPI_BASELINE_PATH="${TERMIT_EVAL_KPI_BASELINE:-$ROOT/data/eval_kpi_baseline.json}"
  python3 "$ROOT/scripts/post_train_model_eval.py" \
    --model "${PRE_TRAIN_MODEL}" \
    --output "${KPI_BASELINE_PATH}"
fi

echo "== 2/5 Export dataset + finetune job (week2) =="
"$ROOT/scripts/training_loop_week2.sh"

if [[ "${USE_MODEL_KPI}" == "true" && "${TERMIT_FINETUNE_AUTO_TRAIN_DPO:-false}" == "true" ]]; then
  echo ""
  echo "== 2c/5 DPO train path (GPU probe) =="
  "${ROOT}/scripts/dpo_gpu_train.sh" || echo "WARN: DPO train path skipped or failed (non-blocking)."
fi

echo ""
if [[ "${USE_MODEL_KPI}" == "true" ]]; then
  echo "== 3/5 Post-train model eval (MB1-MB3) =="
  POST_TRAIN_MODEL="${TERMIT_FINETUNE_OUTPUT_MODEL:-termit-core-ft}"
  POST_TRAIN_MODEL="${POST_TRAIN_MODEL#ollama:}"
  python3 "$ROOT/scripts/post_train_model_eval.py" \
    --model "ollama:${POST_TRAIN_MODEL}" \
    --output "$CURRENT_REPORT" \
    --persist-report
  python3 -m json.tool "$CURRENT_REPORT" | head -30
else
  echo "== 3/5 Eval suite (category=${CATEGORY}, limit=${LIMIT}) =="
  curl_api -X POST "$BASE_URL/api/eval/run-suite" \
    -H "Content-Type: application/json" \
    -d "{\"category\":\"${CATEGORY}\",\"limit\":${LIMIT},\"persist_report\":true}" \
    | tee "$CURRENT_REPORT" \
    | python3 -m json.tool | head -40
fi

echo ""
echo "== 3b/5 Model-bound eval gate (tool scenarios) =="
TERMIT_MODEL_BOUND_GATE_TIER="${TERMIT_MODEL_BOUND_GATE_TIER:-model_bound_ci}" \
  "$ROOT/scripts/model_bound_eval_gate.py" || GATE_OK=1

echo ""
echo "== 4/5 Regression gate vs baseline =="
if [[ "${USE_MODEL_KPI}" == "true" ]]; then
  echo "Skip release regression gate (model KPI mode uses MB1-MB3 pre/post reports)."
elif [[ ! -f "$BASELINE" ]]; then
  echo "Baseline missing: $BASELINE — skip regression gate." >&2
else
  if ! python3 "$ROOT/scripts/eval_regression_report.py" \
    --baseline "$BASELINE" \
    --current "$CURRENT_REPORT" \
    --max-pass-rate-drop "$MAX_DROP"; then
    GATE_OK=1
  fi
fi

if [[ "$GATE_OK" -eq 0 && "${USE_MODEL_KPI}" != "true" && "${TERMIT_EVAL_AUTO_PROMOTE_BASELINE:-false}" == "true" && -f "$BASELINE" ]]; then
  echo ""
  echo "== 4b/5 Promote baseline (gate green) =="
  MIN_IMPROVE="${TERMIT_EVAL_MIN_IMPROVEMENT_FOR_PROMOTE:-0.0}"
  python3 "$ROOT/scripts/eval_baseline_promote.py" \
    --baseline "$BASELINE" \
    --current "$CURRENT_REPORT" \
    --max-pass-rate-drop "$MAX_DROP" \
    --min-improvement "$MIN_IMPROVE"
fi

if [[ "$GATE_OK" -eq 0 ]]; then
  echo ""
  echo "== 4c/5 Eval improvement KPI (+5% target) =="
  KPI_MIN="${TERMIT_FINETUNE_MIN_EVAL_IMPROVEMENT:-0.05}"
  KPI_BASELINE="${TERMIT_EVAL_KPI_BASELINE:-$ROOT/data/eval_kpi_baseline.json}"
  if [[ ! -f "${KPI_BASELINE}" ]]; then
    KPI_BASELINE="${BASELINE}"
  fi
  if [[ -f "${KPI_BASELINE}" ]]; then
    KPI_OUT="${TERMIT_EVAL_KPI_LAST:-$ROOT/data/eval_kpi_last.json}"
    KPI_ARGS=(--baseline "${KPI_BASELINE}" --current "$CURRENT_REPORT" --min-improvement "$KPI_MIN" --output "${KPI_OUT}")
    if [[ "${TERMIT_FINETUNE_KPI_STRICT:-false}" == "true" ]]; then
      KPI_ARGS+=(--strict)
    fi
    python3 "$ROOT/scripts/finetune_eval_kpi_gate.py" "${KPI_ARGS[@]}"
  else
    echo "Skip KPI gate: no baseline at ${KPI_BASELINE} or ${BASELINE}" >&2
  fi
fi

if [[ "$GATE_OK" -ne 0 ]]; then
  exit 1
fi

echo ""
echo "== 5/5 Training dashboard + agent metrics =="
curl_api "$BASE_URL/api/finetune/training/dashboard?limit=5" | python3 -m json.tool | head -40
echo ""
curl_api "$BASE_URL/api/ops/agent-runs/metrics" | python3 -m json.tool | head -20

echo ""
echo "OK — training loop full complete."
echo "Current eval report: $CURRENT_REPORT"
