#!/usr/bin/env bash
# Restart Termit API (stop port + start in background).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${TERMIT_PORT:-8765}"
HOST="${TERMIT_HOST:-127.0.0.1}"
LOG="${ROOT}/.tools/termit-server.log"

"$ROOT/scripts/stop_server.sh"

mkdir -p "${ROOT}/.tools"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi
if [[ -f "${ROOT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT}/.venv/bin/activate"
fi

echo "Starting Termit on ${HOST}:${PORT}..."
cd "$ROOT"
UVICORN_BIN="${PYTHON_BIN}"
if [[ -x "${ROOT}/.venv/bin/uvicorn" ]]; then
  UVICORN_BIN="${ROOT}/.venv/bin/uvicorn"
elif command -v uvicorn >/dev/null 2>&1; then
  UVICORN_BIN="uvicorn"
fi
if command -v setsid >/dev/null 2>&1; then
  setsid nohup "${UVICORN_BIN}" app.main:app --host "$HOST" --port "$PORT" >>"$LOG" 2>&1 < /dev/null &
else
  nohup "${UVICORN_BIN}" app.main:app --host "$HOST" --port "$PORT" >>"$LOG" 2>&1 < /dev/null &
fi
SERVER_PID=$!
disown "$SERVER_PID" 2>/dev/null || true
echo "Server PID: ${SERVER_PID} (log: ${LOG})"

for _ in $(seq 1 60); do
  if curl -fsS --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "Termit ready: http://127.0.0.1:${PORT}"
    curl -s "http://127.0.0.1:${PORT}/healthz" | python3 -m json.tool 2>/dev/null | head -8 || true
    exit 0
  fi
  sleep 0.5
done

echo "error: server did not start. Log: ${LOG}" >&2
tail -20 "$LOG" 2>/dev/null || true
exit 1
