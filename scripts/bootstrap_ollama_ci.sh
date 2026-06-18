#!/usr/bin/env bash
# Download Ollama into .tools, start server, pull a small CI model for live orchestration gate.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OLLAMA_BIN="${ROOT}/.tools/ollama"
OLLAMA_VERSION="${TERMIT_OLLAMA_CI_VERSION:-v0.23.1}"
CI_MODEL="${TERMIT_OLLAMA_CI_MODEL:-tinyllama}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"

cd "$ROOT"
mkdir -p "${ROOT}/.tools"

_ensure_ollama_binary() {
  if [[ -x "${OLLAMA_BIN}" ]]; then
    return 0
  fi
  local os arch archive url extract_dir
  os="$(uname -s)"
  arch="$(uname -m)"
  case "${os}" in
    Darwin)
      archive="${ROOT}/.tools/ollama-darwin.tgz"
      url="https://github.com/ollama/ollama/releases/download/${OLLAMA_VERSION}/ollama-darwin.tgz"
      ;;
    Linux)
      archive="${ROOT}/.tools/ollama-linux.tgz"
      if [[ "${arch}" == "aarch64" || "${arch}" == "arm64" ]]; then
        url="https://github.com/ollama/ollama/releases/download/${OLLAMA_VERSION}/ollama-linux-arm64.tgz"
      else
        url="https://github.com/ollama/ollama/releases/download/${OLLAMA_VERSION}/ollama-linux-amd64.tgz"
      fi
      ;;
    *)
      echo "bootstrap_ollama_ci: unsupported OS ${os}" >&2
      return 1
      ;;
  esac
  echo "Downloading Ollama ${OLLAMA_VERSION} for ${os}/${arch}..."
  curl -fsSL -o "${archive}" "${url}"
  tar -xzf "${archive}" -C "${ROOT}/.tools"
  if [[ ! -x "${OLLAMA_BIN}" ]]; then
    found="$(find "${ROOT}/.tools" -maxdepth 3 -type f -name ollama 2>/dev/null | head -1 || true)"
    if [[ -n "${found}" ]]; then
      cp "${found}" "${OLLAMA_BIN}"
      chmod +x "${OLLAMA_BIN}"
    fi
  fi
  if [[ ! -x "${OLLAMA_BIN}" ]]; then
    echo "bootstrap_ollama_ci: ollama binary not found after extract" >&2
    return 1
  fi
}

_ensure_ollama_binary
"${ROOT}/scripts/start_ollama_local.sh"

if ! curl -sf --max-time 10 "http://${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
  echo "bootstrap_ollama_ci: Ollama not reachable after start" >&2
  exit 1
fi

if ! "${OLLAMA_BIN}" list 2>/dev/null | awk 'NR>1 {print $1}' | grep -q "^${CI_MODEL}"; then
  echo "Pulling CI model: ${CI_MODEL}"
  "${OLLAMA_BIN}" pull "${CI_MODEL}"
fi

echo "OK — Ollama CI bootstrap ready (model=${CI_MODEL}, host=${OLLAMA_HOST})"
