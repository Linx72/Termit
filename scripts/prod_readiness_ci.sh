#!/usr/bin/env bash
# CI / GitHub runners: plan + GPU/cloud preflight без staging (blockers — warn).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export TERMIT_PROD_READINESS_STAGING=false
export TERMIT_PROD_READINESS_STRICT_GPU=false
export TERMIT_PROD_READINESS_DEV_SEED=false

exec "${ROOT}/scripts/prod_readiness_check.sh"
