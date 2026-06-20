#!/usr/bin/env bash
# Full post-release checklist: tests, smoke, push, GitHub release.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
TAG="v${VERSION}"
CURRENT_BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"

echo "== Termit release-all ($TAG) =="

if [[ ! -f "$ROOT/docs/MIGRATION_NOTES_${VERSION}.md" ]]; then
  echo "Hint: run ./scripts/release_pack.sh ${VERSION} --prev PREV --notes 'summary' first"
fi

echo "== 1/5 Pre-release gates =="
PROFILE="${TERMIT_RELEASE_SMOKE_PROFILE:-extended}"
STAGING="${TERMIT_RELEASE_RUN_STAGING:-auto}"
if [[ -x "$ROOT/scripts/pre_release_check.sh" ]]; then
  TERMIT_RELEASE_SMOKE_PROFILE="${PROFILE}" \
  TERMIT_RELEASE_RUN_STAGING="${STAGING}" \
    "$ROOT/scripts/pre_release_check.sh"
else
  TERMIT_RELEASE_SMOKE_PROFILE="${PROFILE}" "$ROOT/scripts/release_gate_local.sh"
fi

echo "== 2/5 Full unittest discover (sanity) =="
"${PYTHON_BIN}" -m unittest discover -s tests -q

echo "== 3/5 Git push =="
if git remote get-url origin >/dev/null 2>&1; then
  git push -u origin "$CURRENT_BRANCH"
  git push origin "$TAG" 2>/dev/null || git push origin "$TAG"
else
  echo "No git remote — skip push"
fi

echo "== 4/5 GitHub release =="
if command -v gh >/dev/null 2>&1; then
  gh release view "$TAG" >/dev/null 2>&1 && echo "Release $TAG already exists" || \
    gh release create "$TAG" --title "Termit ${VERSION}" --generate-notes
else
  echo "Install gh CLI: gh release create $TAG --title 'Termit ${VERSION}' --generate-notes"
fi

if [[ "${TERMIT_RELEASE_BUILD_CLIENTS:-false}" == "true" ]]; then
  echo "== 5/5 Clients build =="
  "$ROOT/scripts/build_clients.sh"
else
  echo "== Optional: clients =="
  echo "  TERMIT_RELEASE_BUILD_CLIENTS=true ./scripts/release_all.sh"
  echo "  или: ./scripts/build_clients.sh"
fi
echo "== Optional: hosted beta =="
echo "  ./scripts/deploy_hosted_beta.sh"

echo "Done."
