#!/usr/bin/env bash
# Accumulate finetune training signals: bootstrap (dev) + agent eval suite + export smoke.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
API_KEY="${TERMIT_API_KEY:-}"
MIN_TRAJECTORY_SAMPLES="${TERMIT_ACCUMULATE_MIN_TRAJECTORY:-10}"
MIN_DPO_PAIRS="${TERMIT_ACCUMULATE_MIN_DPO:-1}"

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="python3"
fi

AUTH=()
if [[ -n "${API_KEY}" ]]; then
  AUTH=(-H "X-API-Key: ${API_KEY}")
fi

curl_auth() {
  if ((${#AUTH[@]})); then
    curl "$@" "${AUTH[@]}"
  else
    curl "$@"
  fi
}

echo "[accumulate] bootstrap training signals (if empty)..."
"${PYTHON}" "${ROOT}/scripts/finetune_bootstrap_signals.py" || true

echo "[accumulate] bootstrap trajectory runs (if < ${MIN_TRAJECTORY_SAMPLES})..."
"${PYTHON}" "${ROOT}/scripts/finetune_bootstrap_trajectory_runs.py" || true

if curl -sf --max-time 3 "${BASE_URL}/health" >/dev/null 2>&1; then
  echo "[accumulate] agent eval suite (tool_loop scenarios)..."
  curl_auth -sf -X POST "${BASE_URL}/api/agents/eval/suite" \
    -H "Content-Type: application/json" \
    -d '{"tool_loop_only":true,"retrieval_path_prefix":"app/","repo_profile":"termit-core"}' \
    | "${PYTHON}" -m json.tool | head -30 || true
else
  echo "[accumulate] server offline — skip live agent eval suite"
fi

echo "[accumulate] DPO export smoke..."
if curl -sf --max-time 5 "${BASE_URL}/health" >/dev/null 2>&1; then
  DPO_JSON="$(curl_auth -sf -X POST "${BASE_URL}/api/finetune/datasets/export-dpo" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"accumulate-check\",\"min_pairs\":${MIN_DPO_PAIRS}}")"
  echo "${DPO_JSON}" | "${PYTHON}" -m json.tool
  PAIR_COUNT="$(echo "${DPO_JSON}" | "${PYTHON}" -c 'import json,sys; print(int(json.load(sys.stdin).get("pair_count",0)))')"
  if [[ "${PAIR_COUNT}" -lt "${MIN_DPO_PAIRS}" ]]; then
    echo "[accumulate] FAIL: pair_count=${PAIR_COUNT} < ${MIN_DPO_PAIRS}" >&2
    exit 1
  fi
else
  echo "[accumulate] server offline — skip DPO smoke"
fi

echo "[accumulate] trajectory SFT export smoke..."
if curl -sf --max-time 5 "${BASE_URL}/health" >/dev/null 2>&1; then
  SFT_JSON="$(curl_auth -sf -X POST "${BASE_URL}/api/finetune/datasets/export-trajectory-sft" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"accumulate-check\",\"min_samples\":${MIN_TRAJECTORY_SAMPLES},\"min_messages\":3}")"
  echo "${SFT_JSON}" | "${PYTHON}" -m json.tool
  SAMPLE_COUNT="$(echo "${SFT_JSON}" | "${PYTHON}" -c 'import json,sys; print(int(json.load(sys.stdin).get("sample_count",0)))')"
  if [[ "${SAMPLE_COUNT}" -lt "${MIN_TRAJECTORY_SAMPLES}" ]]; then
    echo "[accumulate] FAIL: sample_count=${SAMPLE_COUNT} < ${MIN_TRAJECTORY_SAMPLES}" >&2
    exit 1
  fi
else
  echo "[accumulate] server offline — skip trajectory SFT smoke"
fi

echo "[accumulate] done."
