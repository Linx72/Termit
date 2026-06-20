#!/usr/bin/env bash
# macOS nightly: live orchestration gate with local Ollama (skip gracefully if unavailable).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi
OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"

cd "$ROOT"
# На CI venv часто нет; `source … || true` под set -e на macOS bash всё равно падает.
if [[ -f "${ROOT}/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "${ROOT}/.venv/bin/activate"
fi

echo "== macOS nightly live orchestration =="

if [[ "${TERMIT_OLLAMA_CI_BOOTSTRAP:-false}" == "true" ]]; then
  "${ROOT}/scripts/bootstrap_ollama_ci.sh"
fi

if ! command -v ollama >/dev/null 2>&1 && [[ ! -x "${ROOT}/.tools/ollama" ]]; then
  echo "Skip: Ollama not installed."
  exit 0
fi

if ! curl -sf --max-time 5 "http://${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
  if [[ -x "${ROOT}/.tools/ollama" ]]; then
    "${ROOT}/scripts/start_ollama_local.sh" || true
  fi
fi

if ! curl -sf --max-time 5 "http://${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
  echo "Skip: Ollama not reachable at http://${OLLAMA_HOST}"
  exit 0
fi

pick_live_model() {
  local preferred="${TERMIT_ORCH_LIVE_MODEL:-}"
  if [[ -n "${preferred}" ]]; then
    echo "${preferred}"
    return 0
  fi
  local tags_json
  tags_json="$(curl -sf --max-time 5 "http://${OLLAMA_HOST}/api/tags")"
  local candidate
  for candidate in qwen2.5-coder termit-core-ft deepseek-coder tinyllama phi3 smollm; do
    if echo "${tags_json}" | "${PYTHON_BIN}" -c \
      "import json,sys; tag=sys.argv[1]; names={m.get('name','') for m in json.load(sys.stdin).get('models',[])}; raise SystemExit(0 if any(n.startswith(tag) for n in names) else 1)" \
      "${candidate}"; then
      echo "ollama:${candidate}"
      return 0
    fi
  done
  return 1
}

if ! LIVE_MODEL="$(pick_live_model)"; then
  echo "Skip: no supported Ollama model for live gate (qwen2.5-coder / termit-core-ft / deepseek-coder / tinyllama / phi3 / smollm)."
  exit 0
fi
echo "Using live model: ${LIVE_MODEL}"

if ! curl -sf --max-time 5 "${BASE_URL}/health" >/dev/null 2>&1; then
  TERMIT_ORCH_TOOL_LOOP_EXECUTION_ENABLED=true \
  TERMIT_ORCH_EVAL_FIXTURE_CODER=false \
    uvicorn app.main:app --host 127.0.0.1 --port 8765 &
  for _ in $(seq 1 45); do
    curl -sf --max-time 3 "${BASE_URL}/health" >/dev/null 2>&1 && break
    sleep 1
  done
fi

if ! curl -sf --max-time 5 "${BASE_URL}/health" >/dev/null 2>&1; then
  echo "Skip: Termit API not reachable at ${BASE_URL}"
  exit 0
fi

export TERMIT_ORCH_ENABLE_EVAL_FIXTURE=false
export TERMIT_ORCH_LIVE_MODEL="${LIVE_MODEL}"
export TERMIT_ORCH_SKIP_SERVER_RESTART=true
export TERMIT_ORCH_TOOL_LOOP_FALLBACK="${TERMIT_ORCH_TOOL_LOOP_FALLBACK:-true}"
if ! "${ROOT}/scripts/run_live_orchestration_gate.sh"; then
  if [[ "${TERMIT_MACOS_ORCH_REQUIRED:-false}" == "true" ]]; then
    echo "Live orchestration gate failed (TERMIT_MACOS_ORCH_REQUIRED=true)." >&2
    exit 1
  fi
  echo "WARN: live orchestration gate failed — non-blocking skip."
  exit 0
fi

if [[ "${TERMIT_MACOS_ORCH_TRY_STRICT:-false}" == "true" ]]; then
  echo ""
  echo "== Strict live orchestration gate (no fallback) =="
  export TERMIT_ORCH_TOOL_LOOP_FALLBACK=false
  export TERMIT_ORCH_GATE_TIER=strict_live
  if ! "${ROOT}/scripts/run_strict_live_orchestration_gate.sh"; then
    if [[ "${TERMIT_MACOS_ORCH_STRICT_REQUIRED:-false}" == "true" ]]; then
      echo "Strict live orchestration gate failed (TERMIT_MACOS_ORCH_STRICT_REQUIRED=true)." >&2
      exit 1
    fi
    echo "WARN: strict live orchestration gate failed — non-blocking skip."
  fi
fi

echo "OK — macOS live orchestration gate passed."
