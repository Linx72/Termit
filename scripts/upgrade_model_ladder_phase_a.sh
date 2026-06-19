#!/usr/bin/env bash
# Фаза A model ladder: 14B base для termit-core-ft, pull, recreate, warm.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE_MODEL="${TERMIT_MODEL_LADDER_BASE:-qwen2.5-coder:14b}"
FAST_MODEL="${TERMIT_FAST_MODEL:-qwen2.5-coder}"
EMBED_MODEL="${TERMIT_RETRIEVAL_EMBED_MODEL:-nomic-embed-text}"
API_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"

echo "== Termit upgrade model ladder (фаза A) =="
echo "  Base: ${BASE_MODEL}"
echo "  Fast: ${FAST_MODEL}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama не найден — установите Ollama или scripts/start_ollama_local.sh" >&2
  exit 1
fi

if ! curl -sf --max-time 5 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  echo "Ollama не отвечает — запустите: ollama serve" >&2
  exit 1
fi

echo ""
echo "== 1/4 Pull моделей =="
ollama pull "${FAST_MODEL}"
ollama pull "${BASE_MODEL}" || {
  echo "WARN: ${BASE_MODEL} недоступен — пробуем qwen2.5-coder"
  BASE_MODEL="qwen2.5-coder"
  ollama pull "${BASE_MODEL}"
}
ollama pull "${EMBED_MODEL}" || echo "WARN: embed model pull skipped"

echo ""
echo "== 2/4 Recreate termit-core-ft =="
TERMIT_MODEL_LADDER_BASE="${BASE_MODEL}" "${ROOT}/scripts/setup_stage1_adapter.sh"

echo ""
echo "== 3/4 Проверка моделей =="
"${ROOT}/scripts/check_ollama_models.sh"

echo ""
echo "== 4/4 Warm API (если сервер запущен) =="
if curl -sf --max-time 3 "${API_URL}/health" >/dev/null 2>&1; then
  curl -sf -X POST "${API_URL}/api/local/models/warm" | python3 -m json.tool 2>/dev/null || true
else
  echo "API не запущен — после ./scripts/restart_server.sh: curl -X POST ${API_URL}/api/local/models/warm"
fi

echo ""
echo "OK — фаза A ladder применена."
echo "  Рекомендуется в .env:"
echo "    TERMIT_CODE_FALLBACK_MODEL=ollama:${BASE_MODEL}"
echo "    TERMIT_DUAL_PASS_ENABLED=true"
echo "    OPENAI_COMPAT_API_KEY=<ключ>  # cloud validator + benchmark"
echo "  Док: docs/MODEL_LADDER_RU.md"
