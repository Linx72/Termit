#!/usr/bin/env bash
# Backup Termit SQLite databases (memory, tasks, agent runs, quota, cache).
# Usage: ./scripts/backup_sqlite.sh [output_dir]
# Cron example (daily 03:00): 0 3 * * * cd /path/to/Termit && ./scripts/backup_sqlite.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
  _env_get() {
    grep -E "^${1}=" "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'" || true
  }
  TERMIT_MEMORY_SQLITE_PATH="${TERMIT_MEMORY_SQLITE_PATH:-$(_env_get TERMIT_MEMORY_SQLITE_PATH)}"
  TERMIT_TASK_SQLITE_PATH="${TERMIT_TASK_SQLITE_PATH:-$(_env_get TERMIT_TASK_SQLITE_PATH)}"
  TERMIT_AGENT_RUN_SQLITE_PATH="${TERMIT_AGENT_RUN_SQLITE_PATH:-$(_env_get TERMIT_AGENT_RUN_SQLITE_PATH)}"
  TERMIT_QUOTA_SQLITE_PATH="${TERMIT_QUOTA_SQLITE_PATH:-$(_env_get TERMIT_QUOTA_SQLITE_PATH)}"
  TERMIT_RESPONSE_CACHE_SQLITE_PATH="${TERMIT_RESPONSE_CACHE_SQLITE_PATH:-$(_env_get TERMIT_RESPONSE_CACHE_SQLITE_PATH)}"
  TERMIT_AGENT_MEMORY_SQLITE_PATH="${TERMIT_AGENT_MEMORY_SQLITE_PATH:-$(_env_get TERMIT_AGENT_MEMORY_SQLITE_PATH)}"
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${1:-$ROOT/data/backups/$STAMP}"
mkdir -p "$DEST"

paths=(
  "${TERMIT_MEMORY_SQLITE_PATH:-./termit_memory.db}"
  "${TERMIT_TASK_SQLITE_PATH:-./termit_tasks.db}"
  "${TERMIT_AGENT_RUN_SQLITE_PATH:-./termit_agent_runs.db}"
  "${TERMIT_QUOTA_SQLITE_PATH:-./termit_quota.db}"
  "${TERMIT_RESPONSE_CACHE_SQLITE_PATH:-./termit_response_cache.db}"
  "${TERMIT_AGENT_MEMORY_SQLITE_PATH:-./termit_agent_memory.db}"
)

copied=0
for rel in "${paths[@]}"; do
  [[ -z "$rel" ]] && continue
  if [[ "$rel" = /* ]]; then
    src="$rel"
  else
    src="$ROOT/${rel#./}"
  fi
  if [[ -f "$src" ]]; then
    base="$(basename "$src")"
    cp -a "$src" "$DEST/$base"
    if [[ -f "${src}-wal" ]]; then
      cp -a "${src}-wal" "$DEST/${base}-wal"
    fi
    if [[ -f "${src}-shm" ]]; then
      cp -a "${src}-shm" "$DEST/${base}-shm"
    fi
    echo "  $base"
    copied=$((copied + 1))
  fi
done

if [[ "$copied" -eq 0 ]]; then
  echo "No SQLite files found to backup." >&2
  exit 1
fi

echo "Backup complete: $DEST ($copied databases)"
