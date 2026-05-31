#!/usr/bin/env bash
# Start local Ollama from project .tools (no system install required).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OLLAMA_BIN="${ROOT}/.tools/ollama"
LOG_FILE="${ROOT}/.tools/ollama.log"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"

if [[ ! -x "${OLLAMA_BIN}" ]]; then
  echo "error: ${OLLAMA_BIN} not found. Run:" >&2
  echo "  mkdir -p ${ROOT}/.tools && cd ${ROOT}/.tools \\" >&2
  echo "    && curl -fsSL -o ollama-darwin.tgz https://github.com/ollama/ollama/releases/download/v0.23.1/ollama-darwin.tgz \\" >&2
  echo "    && tar -xzf ollama-darwin.tgz && chmod +x ollama" >&2
  exit 1
fi

if curl -fsS "http://${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
  echo "Ollama already running at ${OLLAMA_HOST}"
  exit 0
fi

mkdir -p "${ROOT}/.tools"
nohup "${OLLAMA_BIN}" serve > "${LOG_FILE}" 2>&1 &
sleep 1
if curl -fsS "http://${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
  echo "Ollama started at ${OLLAMA_HOST} (log: ${LOG_FILE})"
else
  echo "error: failed to start Ollama, see ${LOG_FILE}" >&2
  exit 1
fi
