#!/usr/bin/env bash
set -euo pipefail

PROFILE="${TERMIT_SMOKE_HTTP_PROFILE:-extended}"

if [[ "$PROFILE" == "core" ]]; then
  exec ./scripts/smoke_http_core.sh
fi
if [[ "$PROFILE" == "extended" ]]; then
  exec ./scripts/smoke_http_extended.sh
fi

echo "Unknown TERMIT_SMOKE_HTTP_PROFILE='$PROFILE' (expected core|extended)." >&2
exit 2
