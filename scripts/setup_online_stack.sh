#!/usr/bin/env bash
# Start self-hosted web search + optional Playwright browser backend for Termit online agents.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== Termit online stack setup =="

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

# Ensure online-related env keys exist
for line in \
  "TERMIT_SEARCH_PROVIDER=searxng" \
  "TERMIT_SEARCH_API_URL=http://127.0.0.1:8888" \
  "TERMIT_BROWSER_BACKEND=httpx" \
  "TERMIT_ASSIGNMENTS_DIR=./data/assignments"; do
  key="${line%%=*}"
  if ! grep -q "^${key}=" .env 2>/dev/null; then
    echo "$line" >> .env
  fi
done

mkdir -p data/assignments

if command -v docker >/dev/null 2>&1; then
  echo "== Starting SearXNG (web search) on :8888 =="
  docker compose up -d searxng 2>&1 || true
  sleep 2
  if curl -fsS --max-time 5 "http://127.0.0.1:8888/search?q=test&format=json" >/dev/null 2>&1; then
    echo "SearXNG OK at http://127.0.0.1:8888"
  else
    echo "warning: SearXNG not responding yet — check: docker compose logs searxng" >&2
  fi
else
  echo "warning: docker not found — install Docker or set TERMIT_SEARCH_PROVIDER=exa with TERMIT_SEARCH_API_KEY" >&2
fi

if [[ "${TERMIT_INSTALL_PLAYWRIGHT:-}" == "1" ]]; then
  echo "== Installing Playwright (optional browser backend) =="
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -r requirements-online.txt
  playwright install chromium
  if grep -q '^TERMIT_BROWSER_BACKEND=' .env; then
    sed -i.bak 's/^TERMIT_BROWSER_BACKEND=.*/TERMIT_BROWSER_BACKEND=playwright/' .env && rm -f .env.bak
  else
    echo "TERMIT_BROWSER_BACKEND=playwright" >> .env
  fi
  echo "Playwright enabled (TERMIT_BROWSER_BACKEND=playwright)"
fi

echo ""
echo "Done. Next:"
echo "  ./scripts/restart_server.sh"
echo "  POST /api/assignments — create project workspace"
echo "  Agent template: online-project-manager (allow_online=true in UI)"
echo "  Guide: ONLINE_PROJECTS_RU.md"
