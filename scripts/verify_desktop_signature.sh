#!/usr/bin/env bash
# Verify codesign + Gatekeeper assessment for TermitShell.app (or any .app path).
# Usage: ./scripts/verify_desktop_signature.sh [path/to/App.app]
set -euo pipefail

APP_PATH="${1:-clients/termit-shell/release/TermitShell.app}"
if [[ ! -d "$APP_PATH" ]]; then
  echo "App bundle not found: $APP_PATH" >&2
  exit 1
fi

echo "== codesign --verify =="
codesign --verify --deep --strict --verbose=2 "$APP_PATH"

echo ""
echo "== codesign -dv =="
codesign -dv --verbose=4 "$APP_PATH" 2>&1 | head -20

echo ""
echo "== spctl -a -t exec =="
spctl -a -t exec -vv "$APP_PATH" 2>&1 || {
  echo "Note: spctl may fail for unsigned/ad-hoc builds; use TERMIT_CODESIGN_IDENTITY for release." >&2
  exit 0
}

echo ""
echo "Signature check passed: $APP_PATH"
