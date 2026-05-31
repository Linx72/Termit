#!/usr/bin/env bash
# Build Termit desktop app (Electron) into clients/termit-desktop/release/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT/clients/termit-client"
npm install
npm run build
npm test

cd "$ROOT/clients/termit-desktop"
npm install
npm run package

echo "Desktop build output: $ROOT/clients/termit-desktop/release/"
ls -la "$ROOT/clients/termit-desktop/release/" 2>/dev/null || true
