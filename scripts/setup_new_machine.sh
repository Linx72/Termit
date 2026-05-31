#!/usr/bin/env bash
# First-time setup: verify clone/remote, venv, deps, .env from example.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REPO_SSH="git@github.com:Linx72/Termit.git"
REPO_HTTPS="https://github.com/Linx72/Termit.git"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "This directory is not a git clone."
  echo ""
  echo "Clone first:"
  echo "  git clone $REPO_SSH Termit && cd Termit"
  echo "  # or: git clone $REPO_HTTPS Termit && cd Termit"
  echo ""
  echo "Then run this script again."
  exit 1
fi

echo "==> remote"
if git remote get-url origin >/dev/null 2>&1; then
  git remote -v
else
  echo "Adding origin → $REPO_SSH"
  git remote add origin "$REPO_SSH"
fi

echo ""
echo "==> python venv"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  echo "Created .venv"
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo ""
echo "==> pip install"
pip install -q -r requirements.txt

echo ""
echo "==> .env"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — edit API keys and model URLs."
else
  echo ".env already exists (left unchanged)"
fi

echo ""
echo "==> git identity (local repo only, optional)"
echo "If commits fail, set name/email for THIS repo only:"
echo "  git config user.name \"Your Name\""
echo "  git config user.email \"you@example.com\""

echo ""
echo "Setup complete."
echo "  ./scripts/sync_start.sh          # before work"
echo "  ./scripts/sync_finish.sh \"msg\"   # after work"
echo "See SYNC_WORKFLOW.md for full guide."
