#!/usr/bin/env bash
# Установка ComfyUI + SDXL Base для локальной генерации изображений (Termit Media Studio).
#
# Каталог по умолчанию: ../ComfyUI (рядом с репозиторием Termit).
# Примеры:
#   ./scripts/setup_comfy_sdxl.sh
#   TERMIT_COMFY_DIR=~/ai/ComfyUI ./scripts/setup_comfy_sdxl.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMFY_DIR="${TERMIT_COMFY_DIR:-$(dirname "$ROOT")/ComfyUI}"
CHECKPOINT="${TERMIT_MEDIA_COMFY_CHECKPOINT:-sd_xl_base_1.0.safetensors}"
HF_REPO="${TERMIT_COMFY_HF_REPO:-stabilityai/stable-diffusion-xl-base-1.0}"

echo "== Termit ComfyUI + SDXL setup =="
echo "  ComfyUI dir: ${COMFY_DIR}"
echo "  Checkpoint:  ${CHECKPOINT}"

if [[ ! -d "${COMFY_DIR}/.git" ]]; then
  echo "Клонирование ComfyUI..."
  git clone https://github.com/comfyanonymous/ComfyUI.git "${COMFY_DIR}"
else
  echo "ComfyUI уже клонирован: ${COMFY_DIR}"
fi

cd "${COMFY_DIR}"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip
pip install torch torchvision torchaudio
pip install -r requirements.txt

mkdir -p models/checkpoints models/vae

CKPT_PATH="models/checkpoints/${CHECKPOINT}"
if [[ -f "${CKPT_PATH}" ]]; then
  echo "Checkpoint уже есть: ${CKPT_PATH}"
else
  echo "Скачивание SDXL checkpoint (~6.5 GB)..."
  if command -v hf >/dev/null 2>&1; then
    hf download "${HF_REPO}" "${CHECKPOINT}" --local-dir models/checkpoints
  else
    pip install -q huggingface_hub
    python3 - <<PY
from huggingface_hub import hf_hub_download

path = hf_hub_download(
    repo_id="${HF_REPO}",
    filename="${CHECKPOINT}",
    local_dir="models/checkpoints",
)
print(f"OK: {path}")
PY
  fi
fi

# Termit .env hints
if [[ -f "${ROOT}/.env" ]]; then
  for line in \
    "TERMIT_MEDIA_ENABLED=true" \
    "TERMIT_MEDIA_IMAGE_PROVIDER=comfy" \
    "TERMIT_MEDIA_COMFY_URL=http://127.0.0.1:8188" \
    "TERMIT_MEDIA_COMFY_WORKFLOW=./data/media/workflows/sdxl_t2i_api.json" \
    "TERMIT_MEDIA_COMFY_CHECKPOINT=${CHECKPOINT}"; do
    key="${line%%=*}"
    if ! grep -q "^${key}=" "${ROOT}/.env" 2>/dev/null; then
      echo "$line" >> "${ROOT}/.env"
    fi
  done
  echo "Обновлён ${ROOT}/.env (media/comfy ключи)."
fi

echo ""
echo "Готово. Дальше:"
echo "  ./scripts/start_comfy_sidecar.sh"
echo "  ./scripts/check_comfy_health.sh"
echo "  TERMIT_MEDIA_ENABLED=true ./scripts/restart_server.sh"
