#!/usr/bin/env bash
# После релиза: prod readiness + подсказки по секретам и workflows (без деплоя).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"

cd "$ROOT"

echo "== Termit prod handoff (v${VERSION}) =="
echo ""
"${ROOT}/scripts/prod_readiness_ci.sh" || true

echo ""
echo "== GitHub Secrets (Settings → Secrets and variables → Actions) =="
echo "  OPENAI_COMPAT_API_KEY     — cloud benchmark, learning loop judge"
echo "  OPENAI_COMPAT_BASE_URL    — optional, если не default"
echo "  TERMIT_BETA_PROD_URL      — prod API base для beta-prod-gate.yml"
echo "  TERMIT_API_KEY            — optional, если prod auth включён"
echo ""
echo "== Workflows (после секретов) =="
echo "  gh workflow run gpu-dpo-learning-loop.yml"
echo "  gh workflow run beta-prod-gate.yml"
echo "  gh workflow run prod-readiness.yml"
echo "  gh workflow run \"Release Gate Staging\""
echo ""
echo "== Локально =="
echo "  export TERMIT_BETA_PROD_URL=https://your-prod-host"
echo "  ./scripts/beta_prod_gate.sh"
echo "  ./scripts/prod_readiness_check.sh"
echo ""
echo "Release: https://github.com/Linx72/Termit/releases/tag/v${VERSION}"
