#!/usr/bin/env bash
# Build Termit desktop app (Electron) into clients/termit-desktop/release/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v npm >/dev/null 2>&1; then
  if [[ -x "/opt/homebrew/bin/npm" ]]; then
    export PATH="/opt/homebrew/bin:$PATH"
  elif [[ -x "/usr/local/bin/npm" ]]; then
    export PATH="/usr/local/bin:$PATH"
  else
    "$ROOT/scripts/install_node_local.sh"
    NODE_BIN="$(find "$ROOT/.tools" -path '*/bin/npm' 2>/dev/null | head -1)"
    [[ -n "$NODE_BIN" ]] || { echo "error: npm not found" >&2; exit 1; }
    export PATH="$(dirname "$NODE_BIN"):${PATH}"
  fi
fi

cd "$ROOT/clients/termit-client"
npm install
npm run build
npm test

cd "$ROOT/clients/termit-desktop"
npm install
npm run package

echo "Desktop build output: $ROOT/clients/termit-desktop/release/"
ls -la "$ROOT/clients/termit-desktop/release/" 2>/dev/null || true
