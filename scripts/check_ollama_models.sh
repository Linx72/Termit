#!/usr/bin/env bash
# Verify Ollama has models referenced in .env / .env.example (chat + embed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/.env"
EXAMPLE="${ROOT}/.env.example"

if ! command -v ollama >/dev/null 2>&1; then
  echo "error: ollama not in PATH — install from https://ollama.com or run scripts/start_ollama_local.sh" >&2
  exit 1
fi

if ! curl -fsS --max-time 3 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
  echo "error: Ollama not reachable at http://127.0.0.1:11434 — run: ollama serve" >&2
  exit 1
fi

collect_from_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  grep -E '^(TERMIT_(DEFAULT|CODE|ANALYSIS|DEFAULT_FALLBACK|CODE_FALLBACK|ANALYSIS_FALLBACK)_MODEL|TERMIT_RETRIEVAL_EMBED_MODEL)=' "$file" \
    | cut -d= -f2- \
    | tr -d '\r"' \
    | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

TMP_MODELS="$(mktemp)"
trap 'rm -f "$TMP_MODELS"' EXIT
{
  collect_from_file "$EXAMPLE"
  collect_from_file "$ENV_FILE"
} | awk 'NF && !seen[$0]++' >"$TMP_MODELS"

if [[ ! -s "$TMP_MODELS" ]]; then
  echo "error: no model variables found in .env.example" >&2
  exit 1
fi

REQUIRED=()
while IFS= read -r raw || [[ -n "$raw" ]]; do
  [[ -z "$raw" ]] && continue
  if [[ "$raw" == ollama:* ]]; then
    REQUIRED+=("${raw#ollama:}")
  elif [[ "$raw" != *:* ]]; then
    REQUIRED+=("$raw")
  fi
done <"$TMP_MODELS"

if [[ ${#REQUIRED[@]} -eq 0 ]]; then
  echo "No Ollama-prefixed models in config — nothing to check."
  exit 0
fi

INSTALLED=()
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" ]] && continue
  INSTALLED+=("$line")
done < <(ollama list 2>/dev/null | awk 'NR>1 {print $1}')

missing=()
for want in "${REQUIRED[@]}"; do
  found=0
  for have in "${INSTALLED[@]:-}"; do
    if [[ "$have" == "$want" ]] || [[ "$have" == "$want:"* ]]; then
      found=1
      break
    fi
  done
  if [[ "$found" -eq 0 ]]; then
    missing+=("$want")
  fi
done

echo "Required Ollama models (${#REQUIRED[@]}): ${REQUIRED[*]}"
echo "Installed: ${INSTALLED[*]:-none}"

if [[ ${#missing[@]} -gt 0 ]]; then
  echo ""
  echo "Missing models:"
  for m in "${missing[@]}"; do
    echo "  ollama pull $m"
  done
  if [[ "${1:-}" == "--pull-missing" ]]; then
    echo ""
    echo "Pulling missing models..."
    for m in "${missing[@]}"; do
      echo "== ollama pull $m =="
      ollama pull "$m"
    done
    exit 0
  fi
  exit 1
fi

echo "All required Ollama models are present."
exit 0
