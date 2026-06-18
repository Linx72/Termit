#!/usr/bin/env bash
# Do-all plan: закрытие фазы 5 — verify bundle + learning loop + отчёт plan status.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate" 2>/dev/null || true

echo "== Termit do_all_plan (фаза 5) =="

echo ""
echo "== 1/7 Статус плана (до) =="
"${PYTHON_BIN}" "${ROOT}/scripts/plan_status_check.py" --summary-only \
  --output "${TERMIT_PLAN_STATUS_BEFORE:-/tmp/termit_plan_status_before.json}" || true

echo ""
echo "== 2/7 CI verify bundle =="
"${ROOT}/scripts/do_all_verify_ci.sh"

echo ""
echo "== 3/7 Training loop + model KPI (Ollama train) =="
TERMIT_FINETUNE_AUTO_TRAIN="${TERMIT_FINETUNE_AUTO_TRAIN:-true}" \
TERMIT_FINETUNE_KPI_STRICT="${TERMIT_FINETUNE_KPI_STRICT:-false}" \
  "${ROOT}/scripts/training_loop_full.sh"

echo ""
echo "== 4/7 DPO path probe (GPU или dry-run) =="
"${ROOT}/scripts/dpo_gpu_train.sh" || echo "WARN: DPO train пропущен/упал (non-blocking)."

echo ""
echo "== 5/7 Live orchestration gate (fallback разрешён) =="
if [[ "${TERMIT_PLAN_SKIP_LIVE_ORCH:-false}" != "true" ]]; then
  TERMIT_ORCH_TOOL_LOOP_FALLBACK=true \
  TERMIT_ORCH_LIVE_MODEL="${TERMIT_ORCH_LIVE_MODEL:-ollama:qwen2.5-coder}" \
    "${ROOT}/scripts/run_live_orchestration_gate.sh" \
    || echo "WARN: live orchestration gate не прошёл (non-blocking)."
else
  echo "Пропуск (TERMIT_PLAN_SKIP_LIVE_ORCH=true)."
fi

echo ""
echo "== 6/7 Strict live gate (opt-in) =="
if [[ "${TERMIT_PLAN_TRY_STRICT_LIVE:-false}" == "true" ]]; then
  TERMIT_ORCH_LIVE_MODEL="${TERMIT_ORCH_LIVE_MODEL:-ollama:qwen2.5-coder}" \
    "${ROOT}/scripts/run_strict_live_orchestration_gate.sh" \
    || echo "WARN: strict live gate не прошёл (non-blocking)."
else
  echo "Пропуск (TERMIT_PLAN_TRY_STRICT_LIVE=true для включения)."
fi

echo ""
echo "== 7/7 Статус плана (после) =="
PLAN_STRICT="${TERMIT_PLAN_STATUS_STRICT:-false}"
PLAN_ARGS=(--summary-only --output "${TERMIT_PLAN_STATUS_AFTER:-/tmp/termit_plan_status_after.json}")
if [[ "${PLAN_STRICT}" == "true" ]]; then
  PLAN_ARGS+=(--strict)
fi
if ! "${PYTHON_BIN}" "${ROOT}/scripts/plan_status_check.py" "${PLAN_ARGS[@]}"; then
  if [[ "${PLAN_STRICT}" == "true" ]]; then
    echo "Strict plan status не прошёл (фаза 5 KPI/blockers)." >&2
    exit 1
  fi
  echo "WARN: предупреждения фазы 5 остаются (infra шаги OK)."
fi

echo ""
echo "OK — do_all_plan завершён."
echo "  Отчёты: ${TERMIT_PLAN_STATUS_BEFORE:-/tmp/termit_plan_status_before.json}"
echo "          ${TERMIT_PLAN_STATUS_AFTER:-/tmp/termit_plan_status_after.json}"
echo "  Strict product KPI: TERMIT_PLAN_STATUS_STRICT=true ${ROOT}/scripts/plan_status_check.py --strict"
