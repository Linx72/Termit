#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TERMIT_RELEASE_SMOKE_PROFILE=core exec ./scripts/release_smoke.sh "$@"
