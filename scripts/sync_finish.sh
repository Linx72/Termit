#!/usr/bin/env bash
# Stage all tracked changes, commit, and push to origin.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "error: not a git repository ($ROOT)" >&2
  exit 1
fi

MESSAGE="${1:-sync: $(date +%Y-%m-%d)}"
BRANCH="$(git branch --show-current)"

if [[ -z "$BRANCH" ]]; then
  echo "error: detached HEAD — checkout a branch first" >&2
  exit 1
fi

# Block accidental commit of secrets
echo "==> git add -A"
git add -A

if git diff --cached --name-only | grep -qx '\.env'; then
  echo "error: .env is staged — unstage it (see SYNC_WORKFLOW.md)" >&2
  git reset HEAD -- .env 2>/dev/null || true
  exit 1
fi

if git diff --cached --quiet; then
  echo "nothing to commit"
else
  echo "==> git commit"
  git commit -m "$MESSAGE"
fi

echo "==> git push origin $BRANCH"
git push origin "$BRANCH"

echo ""
git status -sb
echo "Done."
