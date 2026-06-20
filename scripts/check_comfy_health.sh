#!/usr/bin/env bash
# Проверка ComfyUI sidecar для Termit Media Studio.
set -euo pipefail

BASE_URL="${TERMIT_MEDIA_COMFY_URL:-http://127.0.0.1:8188}"
CHECKPOINT="${TERMIT_MEDIA_COMFY_CHECKPOINT:-sd_xl_base_1.0.safetensors}"

echo "== ComfyUI health: ${BASE_URL} =="
if ! curl -sf --max-time 5 "${BASE_URL}/system_stats" >/tmp/comfy_stats.json; then
  echo "FAIL: ComfyUI недоступен на ${BASE_URL}" >&2
  echo "Запустите: ./scripts/setup_comfy_sdxl.sh && ./scripts/start_comfy_sidecar.sh" >&2
  exit 1
fi

python3 - <<'PY'
import json
from pathlib import Path

stats = json.loads(Path("/tmp/comfy_stats.json").read_text())
system = stats.get("system") or {}
print(f"ComfyUI version: {system.get('comfyui_version', 'unknown')}")
print(f"PyTorch: {system.get('pytorch_version', 'unknown')}")
PY

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMFY_DIR="${TERMIT_COMFY_DIR:-$(dirname "$ROOT")/ComfyUI}"
CKPT="${COMFY_DIR}/models/checkpoints/${CHECKPOINT}"
if [[ -f "${CKPT}" ]]; then
  echo "OK: checkpoint ${CHECKPOINT}"
else
  echo "WARN: checkpoint не найден: ${CKPT}" >&2
  echo "Запустите: ./scripts/setup_comfy_sdxl.sh" >&2
  exit 1
fi

echo "OK: ComfyUI готов для provider=comfy"
