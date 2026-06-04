#!/usr/bin/env bash
# Unified smoke contour.
# Default is deterministic core profile; use TERMIT_RELEASE_SMOKE_PROFILE=extended for full suite.
# Set TERMIT_SMOKE_REQUIRE_SERVER=1 to fail if :8765 is unreachable.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TERMIT_RELEASE_SMOKE_PROFILE="${TERMIT_RELEASE_SMOKE_PROFILE:-core}" \
  exec ./scripts/release_smoke.sh "$@"
