#!/usr/bin/env bash
# Локальный release gate: extended smoke + plan status dev green (overall_ok).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PROFILE="${TERMIT_RELEASE_SMOKE_PROFILE:-extended}"
echo "== Release gate local (smoke=${PROFILE} + plan dev green) =="

TERMIT_RELEASE_SMOKE_PROFILE="${PROFILE}" "${ROOT}/scripts/release_smoke.sh"
"${ROOT}/scripts/plan_status_dev_green.sh"

echo "OK — release gate local passed."
