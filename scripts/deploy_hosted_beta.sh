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
HOSTED_API_KEY="${TERMIT_API_KEY:-${TERMIT_HOSTED_API_KEY:-}}"
if [[ -z "${HOSTED_API_KEY}" ]] && grep -qE '^TERMIT_AUTH_ENABLED=true' "${ROOT}/.env" 2>/dev/null; then
  HOSTED_API_KEY="viewer-key"
  export TERMIT_HOSTED_AUTH_EXPECT="${TERMIT_HOSTED_AUTH_EXPECT:-true}"
fi
TERMIT_HOSTED_BASE_URL="${BASE_URL}" \
TERMIT_API_KEY="${HOSTED_API_KEY}" \
  "${ROOT}/scripts/hosted_smoke.sh"

echo ""
echo "== 4/4 Plan status snapshot =="
PLAN_CURL=(curl -sf --max-time 10)
if [[ -n "${HOSTED_API_KEY}" ]]; then
  PLAN_CURL+=(-H "X-API-Key: ${HOSTED_API_KEY}")
fi
if "${PLAN_CURL[@]}" "${BASE_URL}/api/ops/plan-status" >/dev/null 2>&1; then
  TERMIT_BASE_URL="${BASE_URL}" \
  TERMIT_API_KEY="${HOSTED_API_KEY}" \
  TERMIT_PLAN_STATUS_SNAPSHOT="${ROOT}/data/plan_status_hosted.json" \
    "${ROOT}/scripts/capture_plan_status_snapshot.sh" || true
fi

echo ""
echo "== 5/5 Beta staging gate (probe, gate_mode=${TERMIT_BETA_GATE_MODE:-real}) =="
TERMIT_HOSTED_BASE_URL="${BASE_URL}" \
TERMIT_BETA_GATE_MODE="${TERMIT_BETA_GATE_MODE:-real}" \
TERMIT_BETA_STAGING_STRICT=false \
  "${ROOT}/scripts/beta_staging_gate.sh" \
  || echo "WARN: beta staging gate not green (expected until real cohort ≥5)."

echo ""
echo "OK — hosted beta готов: ${BASE_URL}"
echo "  Smoke с auth: TERMIT_API_KEY=viewer-key TERMIT_HOSTED_AUTH_EXPECT=true ./scripts/hosted_smoke.sh"
echo "  Prod overlay: TERMIT_COMPOSE_FILES='docker-compose.yml -f docker-compose.prod.yml' ./scripts/deploy_hosted_beta.sh"
