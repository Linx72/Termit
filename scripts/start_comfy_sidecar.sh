#!/usr/bin/env bash
# Запуск ComfyUI sidecar для Termit Media Studio (локальный SDXL).
#
# Примеры:
#   ./scripts/start_comfy_sidecar.sh
#   TERMIT_COMFY_DIR=~/ai/ComfyUI TERMIT_COMFY_PORT=8188 ./scripts/start_comfy_sidecar.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMFY_DIR="${TERMIT_COMFY_DIR:-$(dirname "$ROOT")/ComfyUI}"
PORT="${TERMIT_COMFY_PORT:-8188}"
HOST="${TERMIT_COMFY_HOST:-127.0.0.1}"
PID_FILE="${TERMIT_COMFY_PID_FILE:-${ROOT}/data/ops/comfy_sidecar.pid}"
LOG_FILE="${TERMIT_COMFY_LOG_FILE:-${ROOT}/data/ops/comfy_sidecar.log}"

mkdir -p "$(dirname "$PID_FILE")" "$(dirname "$LOG_FILE")"

echo "== Termit ComfyUI sidecar =="
echo "  Dir:  ${COMFY_DIR}"
echo "  URL:  http://${HOST}:${PORT}"

if curl -sf --max-time 2 "http://${HOST}:${PORT}/system_stats" >/dev/null 2>&1; then
  echo "ComfyUI уже отвечает на http://${HOST}:${PORT}"
  exit 0
fi

if [[ ! -f "${COMFY_DIR}/main.py" ]]; then
  echo "ComfyUI не найден в ${COMFY_DIR}" >&2
  echo "Запустите: ./scripts/setup_comfy_sdxl.sh" >&2
  exit 1
fi

if [[ -f "${PID_FILE}" ]]; then
  old_pid="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${old_pid}" ]] && kill -0 "${old_pid}" 2>/dev/null; then
    echo "ComfyUI процесс ${old_pid} уже запущен, ожидание health..."
  else
    rm -f "${PID_FILE}"
  fi
fi

if ! curl -sf --max-time 2 "http://${HOST}:${PORT}/system_stats" >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source "${COMFY_DIR}/.venv/bin/activate"
  cd "${COMFY_DIR}"
  nohup python main.py --listen "${HOST}" --port "${PORT}" >>"${LOG_FILE}" 2>&1 &
  echo $! > "${PID_FILE}"
  echo "Старт ComfyUI pid=$(cat "${PID_FILE}"), log=${LOG_FILE}"
fi

echo "Ожидание /system_stats (до 120s)..."
for _ in $(seq 1 60); do
  if curl -sf --max-time 2 "http://${HOST}:${PORT}/system_stats" >/dev/null; then
    echo "OK — ComfyUI на http://${HOST}:${PORT}"
    echo "  TERMIT_MEDIA_ENABLED=true"
    echo "  TERMIT_MEDIA_IMAGE_PROVIDER=comfy"
    echo "  TERMIT_MEDIA_COMFY_URL=http://${HOST}:${PORT}"
    exit 0
  fi
  sleep 2
done

echo "WARN: ComfyUI ещё загружается — проверьте: tail -f ${LOG_FILE}" >&2
exit 0
