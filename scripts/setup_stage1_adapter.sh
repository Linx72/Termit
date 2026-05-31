#!/usr/bin/env bash
# Create Ollama model from Stage1 Modelfile and register adapter in Termit.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODELFILE="${ROOT}/data/finetune/recipes/termit-core-ft.Modelfile"
MODEL_NAME="termit-core-ft"
OLLAMA_MODEL="ollama:${MODEL_NAME}"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
ENV_FILE="${ROOT}/deploy/schedulers/stage1-weekly.env"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
fi

find_ollama() {
  if command -v ollama >/dev/null 2>&1; then
    command -v ollama
    return 0
  fi
  for candidate in \
    "${ROOT}/.tools/ollama" \
    /opt/homebrew/bin/ollama \
    /usr/local/bin/ollama \
    /usr/bin/ollama; do
    if [[ -x "${candidate}" ]]; then
      echo "${candidate}"
      return 0
    fi
  done
  return 1
}

echo "==> Modelfile: ${MODELFILE}"
if [[ ! -f "${MODELFILE}" ]]; then
  echo "error: Modelfile not found" >&2
  exit 1
fi

OLLAMA_BIN=""
if OLLAMA_BIN="$(find_ollama)"; then
  echo "==> Creating Ollama model ${MODEL_NAME} (requires base model deepseek-coder pulled)"
  if ! "${OLLAMA_BIN}" list 2>/dev/null | grep -q "deepseek-coder"; then
    echo "==> Pulling deepseek-coder..."
    "${OLLAMA_BIN}" pull deepseek-coder
  fi
  "${OLLAMA_BIN}" create "${MODEL_NAME}" -f "${MODELFILE}"
  echo "==> Ollama model ready: ${OLLAMA_MODEL}"
else
  echo "warn: ollama not found in PATH — skipping model create."
  echo "      Install: https://ollama.com/download"
  echo "      Then re-run: ${ROOT}/scripts/setup_stage1_adapter.sh"
fi

HEADERS=(-H "Content-Type: application/json")
if [[ -n "${TERMIT_API_KEY:-}" ]]; then
  HEADERS+=(-H "X-API-Key: ${TERMIT_API_KEY}")
fi

echo "==> Registering adapter in Termit (${BASE_URL})"
REGISTER_PAYLOAD="$(cat <<EOF
{
  "name": "${MODEL_NAME}",
  "model": "${OLLAMA_MODEL}",
  "base_model": "ollama:deepseek-coder",
  "repo_profile_id": "termit-core",
  "description": "Stage1 weekly-stage1 run ftpbg_ca1f99373af1 (174 samples, baseline 70.8%)"
}
EOF
)"

curl -fsS -X POST "${BASE_URL}/api/finetune/adapters" \
  "${HEADERS[@]}" \
  -d "${REGISTER_PAYLOAD}"
echo
echo "==> Routing profiles:"
curl -fsS "${BASE_URL}/api/routing/profiles" "${HEADERS[@]}" | python3 -m json.tool
