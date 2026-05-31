#!/usr/bin/env bash
# Pull latest from origin/main with rebase and show working tree status.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "error: not a git repository ($ROOT)" >&2
  exit 1
fi

BRANCH="$(git branch --show-current)"
if [[ -z "$BRANCH" ]]; then
  echo "error: detached HEAD — checkout a branch first (e.g. main)" >&2
  exit 1
fi

UPSTREAM="${1:-origin/$BRANCH}"

echo "==> fetch origin"
git fetch origin

echo "==> pull --rebase $UPSTREAM"
if git rev-parse --verify "$UPSTREAM" >/dev/null 2>&1; then
  git pull --rebase "$UPSTREAM"
else
  echo "warning: $UPSTREAM not found; skipping pull (first push?)" >&2
fi

echo ""
echo "==> status"
git status -sb

echo ""
echo "Done. Start working, then run: ./scripts/sync_finish.sh \"your message\""
