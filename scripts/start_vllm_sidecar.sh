#!/usr/bin/env bash
# Запуск vLLM sidecar (Docker) для Termit — ось A inference.
#
# Требуется: Docker + NVIDIA GPU (или CPU fallback с малой моделью).
# Примеры:
#   ./scripts/start_vllm_sidecar.sh
#   VLLM_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct ./scripts/start_vllm_sidecar.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODEL="${VLLM_MODEL:-${TERMIT_VLLM_SERVED_MODEL:-Qwen/Qwen3-Coder-Next}}"
PORT="${TERMIT_VLLM_PORT:-8000}"
CONTAINER="${TERMIT_VLLM_CONTAINER:-termit-vllm}"
IMAGE="${TERMIT_VLLM_IMAGE:-vllm/vllm-openai:latest}"

echo "== Termit vLLM sidecar =="
echo "  Model: ${MODEL}"
echo "  Port:  ${PORT}"

if docker ps --format '{{.Names}}' | grep -qx "${CONTAINER}"; then
  echo "Контейнер ${CONTAINER} уже запущен."
  exit 0
fi

if docker ps -a --format '{{.Names}}' | grep -qx "${CONTAINER}"; then
  echo "Старт существующего контейнера ${CONTAINER}..."
  docker start "${CONTAINER}"
else
  GPU_ARGS=()
  if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_ARGS=(--gpus all)
  else
    echo "WARN: nvidia-smi не найден — vLLM на CPU будет очень медленным." >&2
  fi
  docker run -d --name "${CONTAINER}" \
    "${GPU_ARGS[@]}" \
    -p "${PORT}:8000" \
    -v termit-vllm-cache:/root/.cache/huggingface \
    "${IMAGE}" \
    --model "${MODEL}" \
    --host 0.0.0.0 \
    --port 8000 \
    --dtype auto \
    --max-model-len 32768 \
    --enable-auto-tool-choice \
    --tool-call-parser hermes
fi

echo "Ожидание /v1/models (до 120s)..."
for _ in $(seq 1 60); do
  if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/v1/models" >/dev/null; then
    echo "OK — vLLM на http://127.0.0.1:${PORT}"
    echo "  TERMIT_VLLM_ENABLED=true"
    echo "  TERMIT_VLLM_BASE_URL=http://127.0.0.1:${PORT}"
    echo "  TERMIT_CODE_MODEL=vllm:${MODEL}"
    exit 0
  fi
  sleep 2
done

echo "WARN: vLLM ещё загружает weights — проверьте: docker logs -f ${CONTAINER}" >&2
exit 0
