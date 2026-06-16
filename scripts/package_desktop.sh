#!/usr/bin/env bash
# Build native Termit desktop app (TermitShell.app) with optional codesign + notarization.
#
# Electron was removed; this script wraps package_termit_shell.sh.
#
# Signed release (macOS):
#   export TERMIT_CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
#   export TERMIT_NOTARY_PROFILE="termit-notary"   # xcrun notarytool store-credentials
#   ./scripts/package_desktop.sh
#
# Verify after build:
#   ./scripts/verify_desktop_signature.sh clients/termit-shell/release/TermitShell.app
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/scripts/package_termit_shell.sh" "$@"
