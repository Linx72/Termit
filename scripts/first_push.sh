#!/usr/bin/env bash
# Push main and release tags to GitHub (run once after SSH or PAT is configured).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BRANCH="$(git branch --show-current)"
[[ -n "$BRANCH" ]] || { echo "error: checkout main first" >&2; exit 1; }

echo "==> push origin $BRANCH"
git push -u origin "$BRANCH"

VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION" 2>/dev/null || true)"
if [[ -n "$VERSION" ]] && git rev-parse "v${VERSION}" >/dev/null 2>&1; then
  echo "==> push tag v${VERSION}"
  git push origin "v${VERSION}"
fi

for tag in v0.2.0 v0.3.0 v0.3.1; do
  if git rev-parse "$tag" >/dev/null 2>&1; then
    git push origin "$tag" 2>/dev/null || true
  fi
done

echo "Done. Remote: https://github.com/orosam/Termit"
