#!/usr/bin/env bash
# Start Ollama (optional), Termit API, and desktop app.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/scripts/start_ollama_local.sh" ]]; then
  "$ROOT/scripts/start_ollama_local.sh" || true
fi

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "Creating Python venv..."
  python3 -m venv "$ROOT/.venv"
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  pip install -r "$ROOT/requirements.txt"
else
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi

if ! curl -fsS --max-time 3 "http://127.0.0.1:8765/health" >/dev/null 2>&1; then
  echo "Starting Termit server on :8765..."
  nohup uvicorn app.main:app --host 127.0.0.1 --port 8765 > "$ROOT/.tools/termit-server.log" 2>&1 &
  for _ in $(seq 1 25); do
    if curl -fsS --max-time 2 "http://127.0.0.1:8765/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.4
  done
fi

if ! curl -fsS --max-time 3 "http://127.0.0.1:8765/health" >/dev/null 2>&1; then
  echo "error: Termit server did not start. See $ROOT/.tools/termit-server.log" >&2
  exit 1
fi

echo "Termit API ready: http://127.0.0.1:8765"

if [[ "${1:-}" == "--server-only" ]]; then
  echo "Server-only mode. Press Ctrl+C to stop."
  wait
  exit 0
fi

cd "$ROOT/clients/termit-client"
npm install
npm run build

cd "$ROOT/clients/termit-desktop"
npm install
npm run dev
