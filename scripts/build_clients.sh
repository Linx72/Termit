#!/usr/bin/env bash
# Сборка и smoke termit-client, vscode-extension, termit-desktop.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_TESTS="${TERMIT_CLIENT_RUN_TESTS:-true}"

echo "== Termit clients build =="

echo ""
echo "== 1/3 termit-client =="
(
  cd "${ROOT}/clients/termit-client"
  npm install --no-audit --no-fund
  npm run build
  if [[ "${RUN_TESTS}" == "true" ]]; then
    node --test tests/composer.test.mjs tests/workflows.test.mjs tests/agent-resume.test.mjs
  fi
)

echo ""
echo "== 2/3 vscode-extension =="
(
  cd "${ROOT}/clients/vscode-extension"
  npm install --no-audit --no-fund
  npm run build
)

echo ""
echo "== 3/3 termit-desktop =="
(
  cd "${ROOT}/clients/termit-desktop"
  npm install --no-audit --no-fund
  npm run build
)

echo ""
echo "OK — clients build passed."
