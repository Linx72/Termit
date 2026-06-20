#!/usr/bin/env bash
# Фаза C model ladder: DeepSeek V4-Pro frontier + V4-Flash/V3 fallback chain.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

V4_PRO="${TERMIT_FRONTIER_V4_PRO:-openai_compat:deepseek-ai/DeepSeek-V4-Pro}"
V4_FLASH="${TERMIT_FRONTIER_V4_FLASH:-openai_compat:deepseek-ai/DeepSeek-V4-Flash}"
V3="${TERMIT_FRONTIER_V3_FALLBACK:-openai_compat:deepseek-ai/DeepSeek-V3}"

echo "== Termit upgrade model ladder (фаза C — DeepSeek V4) =="
echo "  Frontier: ${V4_PRO}"
echo "  Chain: ${V4_PRO},${V4_FLASH},${V3}"

echo ""
echo "== 1/3 Cloud benchmark probe =="
PROBE_JSON="$("${PYTHON_BIN}" "${ROOT}/scripts/cloud_benchmark_probe.py")"
echo "${PROBE_JSON}"

echo ""
echo "== 2/3 Рекомендуемые env (добавьте в .env) =="
cat <<EOF
TERMIT_FRONTIER_FALLBACK_MODEL=${V4_PRO}
TERMIT_CLOUD_TEACHER_MODEL=${V4_PRO}
TERMIT_EVAL_BENCHMARK_REFERENCE_MODEL=${V4_PRO}
TERMIT_FRONTIER_FALLBACK_CHAIN=${V4_PRO},${V4_FLASH},${V3}
TERMIT_EVAL_QUALITY_JUDGE_MODEL=${V4_PRO}
OPENAI_COMPAT_API_KEY=<ваш ключ>
# Fallback если V4 недоступен на провайдере:
# TERMIT_EVAL_BENCHMARK_REFERENCE_MODEL=${V3}
EOF

echo ""
echo "== 3/3 Capability benchmark (если API key задан) =="
if [[ -n "${OPENAI_COMPAT_API_KEY:-}" || -n "${OPENAI_API_KEY:-}" ]]; then
  TERMIT_RUN_CLOUD_BENCHMARK="${TERMIT_RUN_CLOUD_BENCHMARK:-true}" \
    TERMIT_CAP_REFRESH_BASELINE="${TERMIT_CAP_REFRESH_BASELINE:-0}" \
    "${ROOT}/scripts/cloud_benchmark_cycle.sh" || echo "WARN: cloud benchmark cycle failed"
else
  echo "SKIP — задайте OPENAI_COMPAT_API_KEY для benchmark vs V4."
fi

echo ""
echo "OK — фаза C ladder documented. Док: docs/MODEL_LADDER_RU.md"
