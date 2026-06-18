#!/usr/bin/env bash
# Deterministic orchestration tool-loop smoke (unit-level, no live LLM).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"
echo "== Orchestration tool-loop smoke (unit) =="
"${PYTHON_BIN}" -m unittest \
  tests.test_multi_agent_orchestrator.MultiAgentOrchestratorTests.test_tool_loop_execution_enabled_runs_tool_actions \
  -q
echo "OK — orchestration tool-loop path verified."
