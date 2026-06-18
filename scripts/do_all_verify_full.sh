#!/usr/bin/env bash
# Full local do-all verify: fixture gates + live orchestration (tool-loop fallback).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export TERMIT_DO_ALL_TRY_LIVE_ORCH=true
export TERMIT_DO_ALL_TRY_DPO_TRAIN=true
export TERMIT_DO_ALL_TRY_STRICT_LIVE_ORCH="${TERMIT_DO_ALL_TRY_STRICT_LIVE_ORCH:-false}"
export TERMIT_DO_ALL_TRY_CLOUD="${TERMIT_DO_ALL_TRY_CLOUD:-false}"
export TERMIT_ORCH_TOOL_LOOP_FALLBACK=true
export TERMIT_ORCH_LIVE_MODEL="${TERMIT_ORCH_LIVE_MODEL:-ollama:qwen2.5-coder}"

exec "${ROOT}/scripts/do_all_verify.sh"
