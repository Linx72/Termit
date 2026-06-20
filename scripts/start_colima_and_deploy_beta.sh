#!/usr/bin/env bash
# Запуск Colima (если установлен) и deploy hosted beta.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker CLI не найден." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  if command -v colima >/dev/null 2>&1; then
    echo "== Запуск Colima =="
    colima start || {
      echo "Colima start failed." >&2
      exit 1
    }
  else
    echo "Docker daemon недоступен. Установите Docker Desktop или Colima." >&2
    exit 1
  fi
fi

exec "${ROOT}/scripts/deploy_hosted_beta.sh"
