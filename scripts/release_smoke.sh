#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
PROFILE="${TERMIT_RELEASE_SMOKE_PROFILE:-core}"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"

if [[ "${PROFILE}" != "core" && "${PROFILE}" != "extended" ]]; then
  echo "Unknown TERMIT_RELEASE_SMOKE_PROFILE='${PROFILE}' (expected core|extended)." >&2
  exit 2
fi

echo "== Release smoke profile: ${PROFILE} =="
echo "== Deterministic core tests =="
"${PYTHON_BIN}" -m unittest \
  tests.test_patch_outcome_and_tuning \
  tests.test_finetune_trajectory_export \
  tests.test_finetune_service \
  tests.test_platform_e2e \
  tests.test_agents_api \
  tests.test_desktop_runtime_mode_smoke \
  tests.test_desktop_runtime_state_smoke \
  tests.test_sprint_top5.SprintTop5Tests.test_confirm_run_rejects_and_resumes \
  tests.test_sprint_top5.SprintTop5Tests.test_confirm_run_keeps_verify_retry_counter_in_checkpoint \
  -q

if [[ "${PROFILE}" == "extended" ]]; then
  echo "== Extended full unittest discover =="
  "${PYTHON_BIN}" -m unittest discover -s tests -q
fi

echo "== Platform/HTTP smoke =="
if "${PYTHON_BIN}" -c "import fastapi" >/dev/null 2>&1 && curl -sf --max-time 2 "$BASE_URL/health" >/dev/null 2>&1; then
  if [[ "${PROFILE}" == "core" ]]; then
    ./scripts/smoke_http_core.sh
  else
    ./scripts/smoke_http_extended.sh
    ./scripts/orchestration_tool_loop_smoke.sh
  fi
else
  echo "Skip smoke_http: fastapi missing or server is unreachable at $BASE_URL."
fi

if curl -sf --max-time 2 "$BASE_URL/health" >/dev/null 2>&1; then
    echo "== Cursor parity eval gate =="
    # Parity slice always uses pass-rate gate; do not inherit release/deep tier from env.
    curl -sf -X POST "$BASE_URL/api/eval/run-suite" \
      -H 'Content-Type: application/json' \
      -d '{"category":"cursor_parity","limit":20,"persist_report":false}' \
      | env -u TERMIT_EVAL_GATE_TIER \
      TERMIT_EVAL_MIN_PASS_RATE="${TERMIT_EVAL_MIN_PASS_RATE:-0.95}" \
      "${PYTHON_BIN}" scripts/eval_ci_gate.py

    echo "== Online research eval slice (web_search stub) =="
    curl -sf -X POST "$BASE_URL/api/eval/run-suite" \
      -H 'Content-Type: application/json' \
      -d '{"category":"online_research","persist_report":false}' \
      | env -u TERMIT_EVAL_GATE_TIER \
      TERMIT_EVAL_MIN_PASS_RATE="${TERMIT_EVAL_MIN_PASS_RATE:-1.0}" \
      "${PYTHON_BIN}" scripts/eval_ci_gate.py

  if [[ "${PROFILE}" == "extended" ]]; then
    echo "== Full eval CI gate =="
    curl -sf -X POST "$BASE_URL/api/eval/run-suite" \
      -H 'Content-Type: application/json' \
      -d '{"persist_report":false}' \
      | TERMIT_EVAL_MIN_PASS_RATE="${TERMIT_EVAL_MIN_PASS_RATE:-0.95}" \
        "${PYTHON_BIN}" scripts/eval_ci_gate.py

    echo "== Model-bound eval gate (CI tier) =="
    TERMIT_MODEL_BOUND_GATE_TIER=model_bound_ci "${PYTHON_BIN}" scripts/model_bound_eval_gate.py

    echo "== Orchestration tool-loop smoke =="
    ./scripts/orchestration_tool_loop_smoke.sh

    echo "== Local orchestration preflight =="
    TERMIT_ORCH_LOCAL_SKIP_SPIKE=true \
    TERMIT_ORCH_SKIP_SERVER_RESTART=true \
      ./scripts/run_local_orchestration_gate.sh

    echo "== DPO GPU train (dry-run if no GPU) =="
    ./scripts/dpo_gpu_train.sh || true

    echo "== Capability quarterly review =="
    TERMIT_CAP_GATE_TIER="${TERMIT_CAP_GATE_TIER:-ci}" \
      ./scripts/capability_quarterly_review.sh

    echo "== Shadow traffic gate =="
    "${PYTHON_BIN}" scripts/shadow_traffic_gate.py --base-url "$BASE_URL" || true
  fi
elif [[ "${TERMIT_SMOKE_REQUIRE_SERVER:-}" == "1" ]]; then
  echo "TERMIT_SMOKE_REQUIRE_SERVER=1 but server not reachable at $BASE_URL" >&2
  exit 1
else
  echo "Server not running on $BASE_URL — skip live eval gates."
fi

if curl -sf --max-time 2 "$BASE_URL/health" >/dev/null 2>&1; then
  "${ROOT}/scripts/reset_eval_patch_fixture.sh" || true
fi

echo "OK — release smoke (${PROFILE}) passed."
