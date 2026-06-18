#!/usr/bin/env bash
# Strict live orchestration gate: без fallback, pass_rate=1.0, нужен JSON tool_actions от модели.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export TERMIT_ORCH_ENABLE_EVAL_FIXTURE=false
export TERMIT_ORCH_SPIKE_USE_FIXTURE=false
export TERMIT_ORCH_TOOL_LOOP_FALLBACK=false
export TERMIT_ORCH_GATE_TIER=strict_live
export TERMIT_ORCH_LIVE_MODEL="${TERMIT_ORCH_LIVE_MODEL:-ollama:qwen2.5-coder}"
export TERMIT_ORCH_SPIKE_MAX_PROMPTS="${TERMIT_ORCH_SPIKE_MAX_PROMPTS:-1}"
export TERMIT_ORCH_SPIKE_TIMEOUT_SECONDS="${TERMIT_ORCH_SPIKE_TIMEOUT_SECONDS:-300}"

RETRIES="${TERMIT_ORCH_STRICT_LIVE_RETRIES:-5}"
attempt=1
while [[ "${attempt}" -le "${RETRIES}" ]]; do
  echo "== Strict live orchestration gate (попытка ${attempt}/${RETRIES}) =="
  if [[ "${attempt}" -gt 1 && "${TERMIT_ORCH_STRICT_RESTART_ON_RETRY:-true}" == "true" ]]; then
    echo "Перезапуск API перед retry..."
    "${ROOT}/scripts/restart_server.sh" >/dev/null 2>&1 || true
    sleep 3
  fi
  if "${ROOT}/scripts/run_live_orchestration_gate.sh"; then
    echo "OK — strict live orchestration gate прошёл на попытке ${attempt}."
    exit 0
  fi
  if [[ "${attempt}" -ge "${RETRIES}" ]]; then
    echo "Strict live orchestration gate не прошёл после ${RETRIES} попыток." >&2
    exit 1
  fi
  echo "WARN: strict live gate попытка ${attempt} не прошла — retry..."
  attempt=$((attempt + 1))
  sleep 5
done
