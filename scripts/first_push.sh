#!/usr/bin/env bash
# Push main and release tags to GitHub (run once after SSH or PAT is configured).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRANCH="$(git branch --show-current)"
[[ -n "$BRANCH" ]] || { echo "error: checkout main first" >&2; exit 1; }

echo "==> push origin $BRANCH"
git push -u origin "$BRANCH"

if git rev-parse v0.2.0 >/dev/null 2>&1; then
  echo "==> push tag v0.2.0"
  git push origin v0.2.0
fi

echo "Done. Remote: https://github.com/orosam/Termit"
