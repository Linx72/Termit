#!/usr/bin/env bash
# Full post-release checklist: tests, smoke, push, GitHub release.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
TAG="v${VERSION}"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"

echo "== Termit release-all ($TAG) =="

echo "== 1/4 Python tests =="
"${PYTHON_BIN}" -m unittest discover -s tests -q

echo "== 2/4 Deterministic release smoke =="
if curl -s --max-time 5 -o /dev/null "http://127.0.0.1:8765/health"; then
  "$ROOT/scripts/release_smoke_core.sh"
else
  echo "Skip HTTP smoke — start server: uvicorn app.main:app --host 127.0.0.1 --port 8765"
fi

echo "== 3/4 Git push =="
if git remote get-url origin >/dev/null 2>&1; then
  git push -u origin main
  git push origin "$TAG" 2>/dev/null || git push origin "$TAG"
else
  echo "No git remote — skip push"
fi

echo "== 4/4 GitHub release =="
if command -v gh >/dev/null 2>&1; then
  gh release view "$TAG" >/dev/null 2>&1 && echo "Release $TAG already exists" || \
    gh release create "$TAG" --title "Termit ${VERSION}" --generate-notes
else
  echo "Install gh CLI: gh release create $TAG --title 'Termit ${VERSION}' --generate-notes"
fi

echo "== Optional: clients =="
echo "  cd clients/termit-client && npm install && npm run build && npm test"
echo "  cd ../vscode-extension && npm install && npm run build"
echo "  cd ../termit-desktop && npm install && npm run build"
echo "== Optional: hosted beta =="
echo "  cp .env.example .env && docker compose up --build -d"
echo "  curl -s http://localhost:8080/api/ops/readiness"

echo "Done."
