#!/usr/bin/env bash
# One-shot local setup: venv, tests, Node for clients, optional GitHub push.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== Termit do_all_setup =="

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

echo "== Python tests =="
python -m unittest discover -s tests -q

"$ROOT/scripts/install_node_local.sh"
NODE_BIN="$(find "$ROOT/.tools" -path '*/bin/npm' 2>/dev/null | head -1)"
[[ -n "$NODE_BIN" ]] || { echo "error: npm not found under .tools" >&2; exit 1; }
export PATH="$(dirname "$NODE_BIN"):${PATH}"

echo "== Build Termit client SDK =="
cd "$ROOT/clients/termit-client"
npm install
npm run build
npm test

echo "== Build Termit desktop =="
cd "$ROOT/clients/termit-desktop"
npm install
npm run build

if ssh -o BatchMode=yes -T git@github.com 2>&1 | grep -qi 'successfully authenticated'; then
  echo "== Git push =="
  cd "$ROOT"
  "$ROOT/scripts/first_push.sh"
else
  echo "== GitHub push skipped (SSH not configured) =="
  echo "Run: $ROOT/scripts/setup_github_ssh.sh"
  echo "Add key at https://github.com/settings/keys then: $ROOT/scripts/first_push.sh"
fi

echo ""
echo "Done. Start app: $ROOT/scripts/run_termit_stack.sh"
