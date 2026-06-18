#!/usr/bin/env bash
# Cloud/model benchmark run → capability gates → optional baseline refresh.
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

SCENARIOS="${TERMIT_CLOUD_BENCHMARK_SCENARIOS:-model_bound}"
RUN_BENCHMARK="${TERMIT_RUN_CLOUD_BENCHMARK:-true}"
GATE_TIER="${TERMIT_CAP_GATE_TIER:-release}"
LIMIT="${TERMIT_CAP_REVIEW_LIMIT:-12}"
BASELINE_PATH="${TERMIT_EVAL_CAPABILITY_BASELINE_PATH:-${ROOT}/data/eval_capability_baseline.json}"
REFRESH="${TERMIT_CAP_REFRESH_BASELINE:-0}"

curl_auth() {
  if [[ -n "${API_KEY}" ]]; then
    curl -sf -H "X-API-Key: ${API_KEY}" "$@"
  else
    curl -sf "$@"
  fi
}

echo "== Cloud benchmark cycle (scenarios=${SCENARIOS}, gate=${GATE_TIER}) =="

if [[ "${RUN_BENCHMARK}" == "true" ]]; then
  PROBE_JSON="$("${PYTHON_BIN}" "${ROOT}/scripts/cloud_benchmark_probe.py")"
  echo "Cloud benchmark probe: ${PROBE_JSON}"
  PROBE_READY="$(
    echo "${PROBE_JSON}" | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin).get('ready', False))"
  )"
  if [[ "${PROBE_READY}" != "True" && "${PROBE_READY}" != "true" ]]; then
    if [[ "${TERMIT_CLOUD_BENCHMARK_REQUIRED:-false}" == "true" ]]; then
      echo "Cloud benchmark not ready and TERMIT_CLOUD_BENCHMARK_REQUIRED=true" >&2
      exit 1
    fi
    echo "Skip benchmark run: cloud probe not ready."
    RUN_BENCHMARK=false
  fi
fi

if [[ "${RUN_BENCHMARK}" == "true" ]]; then
  echo "== 1/3 Model benchmark compare =="
  if ! "${PYTHON_BIN}" "${ROOT}/scripts/benchmark_baselines.py" --scenarios "${SCENARIOS}"; then
    if [[ "${TERMIT_CLOUD_BENCHMARK_REQUIRED:-false}" == "true" ]]; then
      echo "Cloud benchmark failed and TERMIT_CLOUD_BENCHMARK_REQUIRED=true" >&2
      exit 1
    fi
    echo "WARN: benchmark run failed — continuing with capability gates on existing history."
  fi
else
  echo "Skip benchmark run: TERMIT_RUN_CLOUD_BENCHMARK=false"
fi

echo ""
echo "== 2/3 Capability quarterly review =="
TERMIT_CAP_GATE_TIER="${GATE_TIER}" \
TERMIT_CAP_REVIEW_LIMIT="${LIMIT}" \
TERMIT_EVAL_CAPABILITY_BASELINE_PATH="${BASELINE_PATH}" \
TERMIT_CAP_REFRESH_BASELINE=0 \
  "${ROOT}/scripts/capability_quarterly_review.sh"

if [[ "${REFRESH}" == "1" || "${REFRESH}" == "true" || "${REFRESH}" == "yes" ]]; then
  echo ""
  echo "== 3/3 Capability baseline refresh =="
  TERMIT_CAP_REVIEW_LIMIT="${LIMIT}" \
  TERMIT_EVAL_CAPABILITY_BASELINE_PATH="${BASELINE_PATH}" \
    "${ROOT}/scripts/capability_baseline_refresh.sh"
else
  echo ""
  echo "Skip baseline refresh (set TERMIT_CAP_REFRESH_BASELINE=1 to enable)."
fi

if curl_auth --max-time 5 "${BASE_URL}/health" >/dev/null 2>&1; then
  echo ""
  echo "== Capability status snapshot =="
  curl_auth "${BASE_URL}/api/eval/benchmark/capability-review?limit=${LIMIT}" | "${PYTHON_BIN}" -m json.tool | head -20
fi

echo ""
echo "OK — cloud benchmark cycle complete."
