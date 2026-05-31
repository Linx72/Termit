#!/usr/bin/env bash
set -euo pipefail

PLIST="${HOME}/Library/LaunchAgents/com.termit.server.plist"
launchctl bootout "gui/$(id -u)/com.termit.server" 2>/dev/null || true
rm -f "$PLIST"
echo "Removed com.termit.server LaunchAgent."
