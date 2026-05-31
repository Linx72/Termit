#!/usr/bin/env bash
# Start Termit API (correct uvicorn flags — do not use "on http://...").
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HOST="${TERMIT_HOST:-0.0.0.0}"
PORT="${TERMIT_PORT:-8765}"
RELOAD="${TERMIT_RELOAD:-}"
FORCE="${TERMIT_FORCE_START:-}"

health_ok() {
  curl -fsS --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1
}

if lsof -ti :"${PORT}" >/dev/null 2>&1; then
  if health_ok && [[ "$FORCE" != "1" && "$FORCE" != "true" ]]; then
    echo "Termit already running on port ${PORT} — http://127.0.0.1:${PORT}"
    echo "Use: ./scripts/restart_server.sh  (or TERMIT_FORCE_START=1 $0)"
    exit 0
  fi
  echo "Port ${PORT} busy — stopping old process..."
  TERMIT_PORT="$PORT" "$ROOT/scripts/stop_server.sh"
fi

if [[ ! -d "$ROOT/.venv" ]]; then
  python3 -m venv "$ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
pip install -q -r "$ROOT/requirements.txt"

ARGS=(app.main:app --host "$HOST" --port "$PORT")
if [[ "$RELOAD" == "1" || "$RELOAD" == "true" || "$RELOAD" == "yes" ]]; then
  ARGS+=(--reload)
fi

echo "Starting: uvicorn ${ARGS[*]}"
echo "Open: http://127.0.0.1:${PORT}"
exec uvicorn "${ARGS[@]}"
