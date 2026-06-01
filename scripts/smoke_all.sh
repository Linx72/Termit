#!/usr/bin/env bash
# Unified smoke contour: unit tests + platform e2e + live HTTP (when server is up).
# Set TERMIT_SMOKE_REQUIRE_SERVER=1 to fail if :8765 is unreachable.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec ./scripts/release_smoke.sh "$@"
