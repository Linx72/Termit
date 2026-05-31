#!/usr/bin/env bash
# Install macOS LaunchAgent — recommended default: Termit API on every login (port 8765).
# Alternative: ./scripts/start_server.sh (foreground) or ./scripts/restart_server.sh (background).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UVICORN="${ROOT}/.venv/bin/uvicorn"
TEMPLATE="${ROOT}/deploy/launchd/com.termit.server.plist.template"
DEST="${HOME}/Library/LaunchAgents/com.termit.server.plist"

if [[ ! -x "$UVICORN" ]]; then
  echo "error: missing ${UVICORN} — run: python3 -m venv .venv && pip install -r requirements.txt" >&2
  exit 1
fi

mkdir -p "${HOME}/Library/LaunchAgents" "${ROOT}/.tools"
sed \
  -e "s|__TERMIT_ROOT__|${ROOT}|g" \
  -e "s|__TERMIT_UVICORN__|${UVICORN}|g" \
  "$TEMPLATE" >"$DEST"

launchctl bootout "gui/$(id -u)/com.termit.server" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
launchctl enable "gui/$(id -u)/com.termit.server"
launchctl kickstart -k "gui/$(id -u)/com.termit.server"

sleep 2
if curl -fsS --max-time 3 "http://127.0.0.1:8765/health" >/dev/null; then
  echo "LaunchAgent installed. Termit API: http://127.0.0.1:8765"
  echo "Logs: ${ROOT}/.tools/termit-launchd.log (stdout), termit-launchd.err.log (stderr)"
  echo "Uninstall: ./scripts/uninstall_launch_agent.sh"
else
  echo "LaunchAgent installed but health check failed. See ${ROOT}/.tools/termit-launchd.err.log" >&2
  exit 1
fi
