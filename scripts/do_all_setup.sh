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

echo "== Ollama models (optional health check) =="
if [[ "${TERMIT_SKIP_OLLAMA_CHECK:-}" != "1" ]]; then
  chmod +x "$ROOT/scripts/check_ollama_models.sh"
  PULL_FLAG=()
  if [[ "${TERMIT_PULL_OLLAMA_MODELS:-}" == "1" ]]; then
    PULL_FLAG=(--pull-missing)
  fi
  if "$ROOT/scripts/check_ollama_models.sh" "${PULL_FLAG[@]}"; then
    echo "Ollama models OK."
  else
    echo "warning: some Ollama models missing — chat may fail until you ollama pull them." >&2
    echo "  Or rerun with: TERMIT_PULL_OLLAMA_MODELS=1 ./scripts/do_all_setup.sh" >&2
  fi
else
  echo "Skipped (TERMIT_SKIP_OLLAMA_CHECK=1)."
fi

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

echo "== Termit API (background) =="
if [[ "${TERMIT_SKIP_SERVER:-}" != "1" ]]; then
  TERMIT_PORT=8765 "$ROOT/scripts/restart_server.sh" || true
fi

if [[ "${TERMIT_INSTALL_LAUNCH_AGENT:-}" == "1" ]]; then
  "$ROOT/scripts/install_launch_agent.sh" || true
fi

echo ""
echo "Done."
echo "  Web UI:  http://127.0.0.1:8765/"
echo "  Desktop: $ROOT/scripts/run_termit_stack.sh"
echo "  Default server (macOS login): TERMIT_INSTALL_LAUNCH_AGENT=1 ./scripts/do_all_setup.sh"
echo "  Auto-pull Ollama models:      TERMIT_PULL_OLLAMA_MODELS=1 ./scripts/do_all_setup.sh"
echo "  Or now:   ./scripts/install_launch_agent.sh"
echo "  Guide:    $ROOT/START_HERE_RU.md"
