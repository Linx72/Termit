#!/usr/bin/env bash
# Восстановить baseline data/eval_fixtures/patch_sample.txt после eval M2 и patch-сценариев.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${ROOT}/data/eval_fixtures/patch_sample.txt"
mkdir -p "$(dirname "$TARGET")"
printf 'hello world\n' > "$TARGET"
echo "OK — reset ${TARGET}"
