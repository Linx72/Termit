#!/usr/bin/env bash
# Live orchestration gate without eval fixture — requires model returning tool_actions JSON.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export TERMIT_ORCH_ENABLE_EVAL_FIXTURE=false
export TERMIT_ORCH_SPIKE_USE_FIXTURE=false
export TERMIT_ORCH_SPIKE_MAX_PROMPTS="${TERMIT_ORCH_SPIKE_MAX_PROMPTS:-1}"
export TERMIT_ORCH_SPIKE_TIMEOUT_SECONDS="${TERMIT_ORCH_SPIKE_TIMEOUT_SECONDS:-240}"
export TERMIT_ORCH_LIVE_MODEL="${TERMIT_ORCH_LIVE_MODEL:-ollama:termit-core-ft}"
export TERMIT_ORCH_ROUTING_POLICY="${TERMIT_ORCH_ROUTING_POLICY:-default}"
export TERMIT_ORCH_TOOL_LOOP_FALLBACK="${TERMIT_ORCH_TOOL_LOOP_FALLBACK:-true}"

exec "${ROOT}/scripts/run_local_orchestration_gate.sh"
