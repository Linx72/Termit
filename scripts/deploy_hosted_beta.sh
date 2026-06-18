#!/usr/bin/env bash
# Hosted beta: docker compose up + health wait + hosted_smoke.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE_URL="${TERMIT_HOSTED_BASE_URL:-http://127.0.0.1:8080}"
COMPOSE_FILES="${TERMIT_COMPOSE_FILES:-docker-compose.yml}"
WAIT_SECONDS="${TERMIT_HOSTED_WAIT_SECONDS:-120}"

echo "== Termit deploy hosted beta =="

if ! command -v docker >/dev/null 2>&1; then
  echo "docker не найден — установите Docker / Colima." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon недоступен — запустите Colima/Docker Desktop." >&2
  exit 1
fi

if [[ ! -f "${ROOT}/.env" ]]; then
  if [[ -f "${ROOT}/deploy/docker.env.example" ]]; then
    cp "${ROOT}/deploy/docker.env.example" "${ROOT}/.env"
    echo "Создан .env из deploy/docker.env.example"
  else
    cp "${ROOT}/.env.example" "${ROOT}/.env"
    echo "Создан .env из .env.example"
  fi
fi

echo ""
echo "== 1/4 Docker compose up =="
docker compose -f "${COMPOSE_FILES}" up --build -d

echo ""
echo "== 2/4 Ожидание health через Caddy (${BASE_URL}) =="
ready=false
for i in $(seq 1 "${WAIT_SECONDS}"); do
  if curl -sf --max-time 3 "${BASE_URL}/health" >/dev/null 2>&1; then
    ready=true
    echo "Health OK (${i}s)"
    break
  fi
  sleep 1
done
if [[ "${ready}" != "true" ]]; then
  echo "Health не ответил за ${WAIT_SECONDS}s на ${BASE_URL}" >&2
  docker compose -f "${COMPOSE_FILES}" ps
  exit 1
fi

echo ""
echo "== 3/4 Hosted smoke =="
TERMIT_HOSTED_BASE_URL="${BASE_URL}" "${ROOT}/scripts/hosted_smoke.sh"

echo ""
echo "== 4/4 Plan status snapshot =="
if curl -sf --max-time 10 "${BASE_URL}/api/ops/plan-status" >/dev/null 2>&1; then
  TERMIT_BASE_URL="${BASE_URL}" \
  TERMIT_PLAN_STATUS_SNAPSHOT="${ROOT}/data/plan_status_hosted.json" \
    "${ROOT}/scripts/capture_plan_status_snapshot.sh" || true
fi

echo ""
echo "OK — hosted beta готов: ${BASE_URL}"
echo "  Smoke с auth: TERMIT_API_KEY=viewer-key TERMIT_HOSTED_AUTH_EXPECT=true ./scripts/hosted_smoke.sh"
echo "  Prod overlay: TERMIT_COMPOSE_FILES='docker-compose.yml -f docker-compose.prod.yml' ./scripts/deploy_hosted_beta.sh"
