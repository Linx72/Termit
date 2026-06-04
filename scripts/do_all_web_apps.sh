#!/usr/bin/env bash
# Full web-apps stack: online search, Playwright optional, seed agents, restart API.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
chmod +x scripts/*.sh

echo "== Termit do_all_web_apps =="

./scripts/setup_online_stack.sh

if [[ "${TERMIT_INSTALL_PLAYWRIGHT:-1}" == "1" ]]; then
  TERMIT_INSTALL_PLAYWRIGHT=1 ./scripts/setup_online_stack.sh
fi

./scripts/seed_web_agents.sh

if [[ "${TERMIT_SKIP_SERVER:-}" != "1" ]]; then
  ./scripts/restart_server.sh || true
fi

echo ""
echo "Done. Open desktop → Assignments / Terminal tabs."
echo "  Guide: WEB_APPS_RU.md + ONLINE_PROJECTS_RU.md"
