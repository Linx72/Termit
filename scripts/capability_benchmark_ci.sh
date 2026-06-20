#!/usr/bin/env bash
# CI-safe capability benchmark: local Termit vs reference (нужен ключ для reference/judge).
# Без ключа — probe + capability review на истории; с dev stub — green probe only.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

cd "$ROOT"

echo "== Capability benchmark CI (V4 ladder) =="

PROBE_JSON="$("${PYTHON_BIN}" "${ROOT}/scripts/cloud_benchmark_probe.py")"
echo "${PROBE_JSON}"

PROBE_READY="$(
  echo "${PROBE_JSON}" | "${PYTHON_BIN}" -c "import json,sys; print(json.load(sys.stdin).get('ready', False))"
)"

if [[ "${PROBE_READY}" == "True" || "${PROBE_READY}" == "true" ]]; then
  echo ""
  echo "== Run model benchmark compare =="
  "${PYTHON_BIN}" "${ROOT}/scripts/benchmark_baselines.py" --scenarios model
else
  echo ""
  echo "SKIP live compare — capability review on history"
  "${PYTHON_BIN}" "${ROOT}/scripts/benchmark_baselines.py" --capability-review --capability-limit 6
fi

echo ""
echo "OK — capability benchmark CI complete."
