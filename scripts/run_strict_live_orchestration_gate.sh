#!/usr/bin/env bash
# Strict live orchestration gate: no tool-loop fallback, pass_rate=1.0, real model JSON required.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export TERMIT_ORCH_ENABLE_EVAL_FIXTURE=false
export TERMIT_ORCH_SPIKE_USE_FIXTURE=false
export TERMIT_ORCH_TOOL_LOOP_FALLBACK=false
export TERMIT_ORCH_GATE_TIER=strict_live
export TERMIT_ORCH_LIVE_MODEL="${TERMIT_ORCH_LIVE_MODEL:-ollama:qwen2.5-coder}"
export TERMIT_ORCH_SPIKE_MAX_PROMPTS="${TERMIT_ORCH_SPIKE_MAX_PROMPTS:-1}"
export TERMIT_ORCH_SPIKE_TIMEOUT_SECONDS="${TERMIT_ORCH_SPIKE_TIMEOUT_SECONDS:-300}"

exec "${ROOT}/scripts/run_live_orchestration_gate.sh"
