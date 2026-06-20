#!/usr/bin/env bash
# Фаза B model ladder: vLLM sidecar + Qwen3-Coder-Next для coding agents.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VLLM_MODEL="${VLLM_MODEL:-${TERMIT_VLLM_SERVED_MODEL:-Qwen/Qwen3-Coder-Next}}"
FAST_MODEL="${TERMIT_FAST_MODEL:-ollama:qwen2.5-coder}"
FALLBACK_MODEL="${TERMIT_CODE_FALLBACK_MODEL:-ollama:qwen2.5-coder:14b}"
API_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"

echo "== Termit upgrade model ladder (фаза B — vLLM) =="
echo "  vLLM model: ${VLLM_MODEL}"
echo "  Fast (Ollama): ${FAST_MODEL}"

echo ""
echo "== 1/4 Ollama fast path (tab/FIM) =="
if command -v ollama >/dev/null 2>&1 && curl -sf --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  BARE_FAST="${FAST_MODEL#ollama:}"
  ollama pull "${BARE_FAST}" || echo "WARN: fast model pull skipped"
else
  echo "Ollama не запущен — fast path останется как в .env"
fi

echo ""
echo "== 2/4 vLLM sidecar =="
chmod +x "${ROOT}/scripts/start_vllm_sidecar.sh" "${ROOT}/scripts/check_vllm_models.sh"
VLLM_MODEL="${VLLM_MODEL}" "${ROOT}/scripts/start_vllm_sidecar.sh" || {
  echo "WARN: vLLM sidecar не поднялся — остаёмся на Ollama (фаза A)" >&2
  "${ROOT}/scripts/upgrade_model_ladder_phase_a.sh"
  exit 0
}

echo ""
echo "== 3/4 Проверка vLLM =="
TERMIT_VLLM_SERVED_MODEL="${VLLM_MODEL}" "${ROOT}/scripts/check_vllm_models.sh" || true

echo ""
echo "== 4/4 Smoke Termit API (если запущен) =="
if curl -sf --max-time 3 "${API_URL}/health" >/dev/null 2>&1; then
  curl -sf "${API_URL}/api/local/runtime/status" | python3 -m json.tool 2>/dev/null | head -40 || true
else
  echo "API не запущен — после restart задайте в .env:"
fi

cat <<EOF

OK — фаза B ladder (рекомендуемый .env):

  TERMIT_VLLM_ENABLED=true
  TERMIT_VLLM_BASE_URL=http://127.0.0.1:8000
  TERMIT_VLLM_SERVED_MODEL=${VLLM_MODEL}
  TERMIT_CODE_MODEL=vllm:${VLLM_MODEL}
  TERMIT_FAST_MODEL=${FAST_MODEL}
  TERMIT_CODE_FALLBACK_MODEL=${FALLBACK_MODEL}
  TERMIT_DEFAULT_MODEL=vllm:${VLLM_MODEL}

Docker prod: docker compose -f docker-compose.yml -f docker-compose.vllm.yml --profile vllm up -d
Док: docs/MODEL_LADDER_RU.md
EOF
