#!/usr/bin/env bash
# Stop Termit API on TERMIT_PORT (default 8765).
set -euo pipefail

PORT="${TERMIT_PORT:-8765}"
PIDS="$(lsof -ti :"${PORT}" 2>/dev/null || true)"

if [[ -z "$PIDS" ]]; then
  echo "No process listening on port ${PORT}."
  exit 0
fi

echo "Stopping process(es) on port ${PORT}: ${PIDS}"
kill $PIDS 2>/dev/null || true
sleep 1
if lsof -ti :"${PORT}" >/dev/null 2>&1; then
  echo "Force stop..."
  kill -9 $(lsof -ti :"${PORT}") 2>/dev/null || true
  sleep 0.5
fi

if lsof -ti :"${PORT}" >/dev/null 2>&1; then
  echo "error: port ${PORT} still in use" >&2
  exit 1
fi

echo "Port ${PORT} is free."
