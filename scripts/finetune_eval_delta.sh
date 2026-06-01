#!/usr/bin/env bash
# Baseline eval -> optional train -> post-eval -> delta report (+ jsonl append).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
API_KEY="${TERMIT_API_KEY:-}"
EVAL_LIMIT="${TERMIT_EVAL_DELTA_LIMIT:-24}"
RUN_TRAIN="${TERMIT_EVAL_DELTA_RUN_TRAIN:-false}"
REPORTS="${TERMIT_EVAL_REPORTS_PATH:-${ROOT}/data/eval_reports.jsonl}"

PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="python3"
fi

AUTH=()
if [[ -n "${API_KEY}" ]]; then
  AUTH=(-H "X-API-Key: ${API_KEY}")
fi

if ! curl -sf --max-time 3 "${BASE_URL}/health" >/dev/null 2>&1; then
  echo "[finetune_eval_delta] server not reachable at ${BASE_URL}" >&2
  exit 1
fi

echo "[finetune_eval_delta] baseline eval..."
BASELINE_JSON="$(curl -sf "${AUTH[@]}" -X POST "${BASE_URL}/api/eval/run-suite" \
  -H "Content-Type: application/json" \
  -d "{\"limit\":${EVAL_LIMIT},\"persist_report\":true,\"tag\":\"finetune-baseline\"}")"
echo "${BASELINE_JSON}" | "${PYTHON}" -m json.tool | head -20
BASELINE_RATE="$(echo "${BASELINE_JSON}" | "${PYTHON}" -c 'import json,sys; print(json.load(sys.stdin).get("pass_rate",0))')"

if [[ "${RUN_TRAIN}" == "true" ]]; then
  echo "[finetune_eval_delta] train cycle..."
  TERMIT_FINETUNE_RUN_STAGE1=true "${ROOT}/scripts/finetune_continuous_learning.sh"
fi

echo "[finetune_eval_delta] post-finetune eval..."
POST_JSON="$(curl -sf "${AUTH[@]}" -X POST "${BASE_URL}/api/eval/run-suite" \
  -H "Content-Type: application/json" \
  -d "{\"limit\":${EVAL_LIMIT},\"persist_report\":true,\"tag\":\"finetune-post\"}")"
echo "${POST_JSON}" | "${PYTHON}" -m json.tool | head -20

DELTA_JSON="$("${PYTHON}" -c '
import json, sys
from datetime import datetime, timezone

baseline = json.loads(sys.argv[1])
post = json.loads(sys.argv[2])
b = float(baseline.get("pass_rate", 0))
p = float(post.get("pass_rate", 0))
payload = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "kind": "finetune_eval_delta",
    "baseline_pass_rate": b,
    "post_pass_rate": p,
    "delta": p - b,
    "baseline_total": int(baseline.get("total", 0)),
    "post_total": int(post.get("total", 0)),
    "baseline_passed": int(baseline.get("passed", 0)),
    "post_passed": int(post.get("passed", 0)),
}
print(json.dumps(payload, ensure_ascii=True))
' "${BASELINE_JSON}" "${POST_JSON}")"

echo "${DELTA_JSON}" | "${PYTHON}" -m json.tool
mkdir -p "$(dirname "${REPORTS}")"
echo "${DELTA_JSON}" >> "${REPORTS}"

GATE_INPUT="$(echo "${POST_JSON}" | "${PYTHON}" -c '
import json, sys
post = json.load(sys.stdin)
post["baseline_pass_rate"] = float(sys.argv[1])
print(json.dumps(post))
' "${BASELINE_RATE}")"

echo "[finetune_eval_delta] regression gate (delta >= 0)..."
TERMIT_EVAL_DELTA_GATE=true TERMIT_FINETUNE_MIN_EVAL_DELTA=0 \
  echo "${GATE_INPUT}" | "${PYTHON}" "${ROOT}/scripts/eval_ci_gate.py"

echo "[finetune_eval_delta] done."
