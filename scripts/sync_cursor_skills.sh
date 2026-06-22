#!/usr/bin/env bash
# Sync runtime skills (data/skills) into .cursor/skills for Cursor IDE parity.
# Cursor-only skills (termit-agent, termit-automation, termit-prompts) are preserved.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/data/skills"
DEST="$ROOT/.cursor/skills"

if [[ ! -d "$SRC" ]]; then
  echo "Missing source: $SRC" >&2
  exit 1
fi

mkdir -p "$DEST"

for skill_dir in "$SRC"/*/; do
  skill_id="$(basename "$skill_dir")"
  skill_file="$skill_dir/SKILL.md"
  if [[ ! -f "$skill_file" ]]; then
    continue
  fi
  target_dir="$DEST/$skill_id"
  mkdir -p "$target_dir"
  cp "$skill_file" "$target_dir/SKILL.md"
  echo "synced: $skill_id"
done

echo "Done. Cursor-only skills in .cursor/skills were not removed."
