#!/usr/bin/env bash
# Проверка vLLM sidecar: /v1/models и served model.
set -euo pipefail

BASE_URL="${TERMIT_VLLM_BASE_URL:-http://127.0.0.1:8000}"
SERVED="${TERMIT_VLLM_SERVED_MODEL:-Qwen/Qwen3-Coder-Next}"

echo "== vLLM health: ${BASE_URL} =="
if ! curl -sf --max-time 5 "${BASE_URL}/v1/models" >/tmp/vllm_models.json; then
  echo "FAIL: vLLM недоступен на ${BASE_URL}" >&2
  echo "Запустите: ./scripts/start_vllm_sidecar.sh" >&2
  exit 1
fi

python3 - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(Path("/tmp/vllm_models.json").read_text())
models = [item.get("id", "") for item in payload.get("data", [])]
served = os.environ.get("TERMIT_VLLM_SERVED_MODEL", "Qwen/Qwen3-Coder-Next")
print(f"models listed: {len(models)}")
for name in models[:10]:
    print(f"  - {name}")
if served in models or any(served in item for item in models):
    print(f"OK: served model present ({served})")
else:
    print(f"WARN: {served} not in /v1/models (vLLM may still be loading weights)")
PY
