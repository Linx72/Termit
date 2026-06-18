#!/usr/bin/env bash
# Quarterly capability review with baseline refresh (Jan/Apr/Jul/Oct cron).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export TERMIT_CAP_GATE_TIER="${TERMIT_CAP_GATE_TIER:-release}"
export TERMIT_CAP_REFRESH_BASELINE="${TERMIT_CAP_REFRESH_BASELINE:-1}"
export TERMIT_EVAL_CAPABILITY_BASELINE_PATH="${TERMIT_EVAL_CAPABILITY_BASELINE_PATH:-$ROOT/data/eval_capability_baseline.json}"

exec "$ROOT/scripts/capability_quarterly_review.sh"
