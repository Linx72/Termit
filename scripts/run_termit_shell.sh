#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT/clients/termit-client"
npm install
npm run build

cd "$ROOT/clients/termit-desktop"
npm install
npx vite build

cd "$ROOT/clients/termit-shell"
swift build -c release

exec .build/release/termit-shell \
  --renderer-root "$ROOT/clients/termit-desktop/dist" \
  --docs-root "$ROOT/clients/termit-desktop/docs/pdf"
