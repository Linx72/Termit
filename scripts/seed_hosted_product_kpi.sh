#!/usr/bin/env bash
# Product KPI dev seed внутри docker compose termit + reload telemetry на :8080.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILES="${TERMIT_COMPOSE_FILES:-docker-compose.yml}"
BASE_URL="${TERMIT_HOSTED_BASE_URL:-http://127.0.0.1:8080}"

cd "$ROOT"

if ! docker compose -f "${COMPOSE_FILES}" ps --status running --services 2>/dev/null | grep -qx termit; then
  echo "Сервис termit не запущен — skip hosted KPI seed." >&2
  exit 0
fi

echo "== Seed product KPI in container (tool-loop + chat metrics) =="
docker compose -f "${COMPOSE_FILES}" exec -T termit \
  python scripts/seed_product_kpi_dev.py --force --runs "${TERMIT_HOSTED_KPI_SEED_RUNS:-150}" --chats 0

echo ""
echo "== Reload dev metrics seed via proxy =="
curl -sf -X POST "${BASE_URL}/api/ops/reload-dev-metrics-seed" \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool | head -8

echo ""
echo "OK — hosted product KPI seed applied."
