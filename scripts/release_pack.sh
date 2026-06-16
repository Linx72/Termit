#!/usr/bin/env bash
# Generate release handoff artifacts: CHANGELOG stub, migration notes, rollback plan.
# Usage:
#   ./scripts/release_pack.sh [version] [--prev PREV] [--notes "summary"]
# Example:
#   ./scripts/release_pack.sh 0.3.6 --prev 0.3.5 --notes "Desktop runtime status bar"
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-$(tr -d '[:space:]' < "$ROOT/VERSION")}"
shift || true

PREV=""
NOTES=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prev)
      PREV="${2:-}"
      shift 2
      ;;
    --notes)
      NOTES="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "$PREV" ]]; then
  PREV="$(grep -m1 '^\## \[' "$ROOT/CHANGELOG.md" | sed -E 's/^## \[(.+)\].*/\1/')"
fi

DATE="$(date +%Y-%m-%d)"
MIGRATION="$ROOT/docs/MIGRATION_NOTES_${VERSION}.md"
ROLLBACK="$ROOT/docs/ROLLBACK_PLAN_${VERSION}.md"
TAG="v${VERSION}"
PREV_TAG="v${PREV}"

if [[ -f "$MIGRATION" || -f "$ROLLBACK" ]]; then
  echo "Refusing to overwrite existing release pack for ${VERSION}." >&2
  echo "  migration: $MIGRATION" >&2
  echo "  rollback:  $ROLLBACK" >&2
  exit 1
fi

SUMMARY="${NOTES:-Stability and product improvements for Termit ${VERSION}.}"

cat > "$MIGRATION" <<EOF
# Migration Notes ${VERSION}

## Scope

${SUMMARY}

Previous stable: \`${PREV_TAG}\`.

## Configuration changes

- Review \`.env.example\` for new or renamed keys since \`${PREV_TAG}\`.
- No schema migrations expected unless noted in commit history.

## CI / release process

- Fast gate (PR/main): \`.github/workflows/ci.yml\`
- Deep gate (nightly): full eval suite in CI
- Release gate (local/manual): \`TERMIT_EVAL_GATE_TIER=release ./scripts/release_smoke_extended.sh\`
- Deterministic core: \`./scripts/release_smoke_core.sh\`

## Operator checks after upgrade

1. \`./scripts/release_smoke_core.sh\`
2. \`GET /health\`, \`GET /healthz\`, \`GET /api/ops/readiness\` => 200
3. Desktop (if used): \`cd clients/termit-desktop && npm run build\`

EOF

cat > "$ROLLBACK" <<EOF
# Rollback Plan ${VERSION}

## Rollback triggers

- Core smoke (\`./scripts/release_smoke_core.sh\`) fails on previously green paths
- Sustained CI regression on \`main\` after deploy
- Critical runtime incident (auth, data loss, queue stuck)

## Fast rollback steps

1. Roll back to previous stable tag (\`${PREV_TAG}\`).
2. Restart Termit API/runtime (\`docker compose up -d --build\` or systemd/LaunchAgent).
3. Smoke:
   - \`/health\`, \`/healthz\`, \`/api/metrics/thresholds\`, \`/api/ops/readiness\`
4. \`./scripts/release_smoke_core.sh\`

## Data compatibility

- Check commit history for SQLite schema or data migrations since \`${PREV_TAG}\`.
- Backup \`data/\` and SQLite path before rollback if migrations were applied.

## Validation after rollback

- \`./.venv/bin/python -m unittest discover -s tests -q\`
- \`./scripts/smoke_http_core.sh\`

## Communication template

- Incident: "Rolled back from ${TAG} to ${PREV_TAG} due to <reason>."
- Impact window: <start> - <end>
- Next action: fix on branch, re-run release pack, re-ship patch/hotfix

EOF

if ! grep -q "^\## \[${VERSION}\]" "$ROOT/CHANGELOG.md"; then
  tmp="$(mktemp)"
  {
    echo "# Changelog"
    echo ""
    echo "## [${VERSION}] - ${DATE}"
    echo ""
    echo "### Added"
    echo "- ${SUMMARY}"
    echo ""
    tail -n +2 "$ROOT/CHANGELOG.md"
  } > "$tmp"
  mv "$tmp" "$ROOT/CHANGELOG.md"
fi

echo "Release pack for ${VERSION} (prev ${PREV_TAG}):"
echo "  $MIGRATION"
echo "  $ROLLBACK"
echo "  CHANGELOG.md section [${VERSION}]"
echo ""
echo "Next: edit CHANGELOG, bump VERSION, tag ${TAG}, run ./scripts/release_all.sh"
