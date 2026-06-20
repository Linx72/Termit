#!/usr/bin/env bash
# Week-2 training loop: export curated dataset from signals → validate job → show KPI dashboard.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${TERMIT_BASE_URL:-http://127.0.0.1:8765}"
DATASET_NAME="${TERMIT_TRAINING_DATASET_NAME:-week2-signals}"

cd "$ROOT"
source .venv/bin/activate 2>/dev/null || true

echo "== 1/4 Export dataset from training signals =="
EXPORT_JSON="$(python3 scripts/finetune_export.py --name "$DATASET_NAME" --min-samples 1)"
echo "$EXPORT_JSON"
DATASET_PATH="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['dataset_path'])" "$EXPORT_JSON")"
SAMPLE_COUNT="$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['sample_count'])" "$EXPORT_JSON")"
echo "Dataset: $DATASET_PATH ($SAMPLE_COUNT samples)"

echo ""
echo "== 1b/5 DPO export + contract gate =="
DPO_EXPORT_OK=0
if [[ "${TERMIT_FINETUNE_AUTO_TRAIN_DPO:-false}" == "true" ]]; then
  if "${ROOT}/scripts/dpo_gpu_train.sh"; then
    DPO_EXPORT_OK=1
    DPO_JSON="$(ls -t "${ROOT}"/data/finetune/datasets/*_dpo_*.jsonl 2>/dev/null | head -1 || true)"
    if [[ -n "${DPO_JSON}" ]]; then
      "${PYTHON:-python3}" "${ROOT}/scripts/eval_dpo_contract_gate.py" --dataset "${DPO_JSON}"
    fi
  else
    echo "DPO GPU train path failed or skipped."
  fi
elif "${PYTHON:-python3}" "${ROOT}/scripts/finetune_dpo_pipeline.py" --name "${DATASET_NAME}-dpo"; then
  DPO_EXPORT_OK=1
  DPO_JSON="$(ls -t "${ROOT}"/data/finetune/datasets/*_dpo_*.jsonl 2>/dev/null | head -1 || true)"
  if [[ -n "${DPO_JSON}" ]]; then
    "${PYTHON:-python3}" "${ROOT}/scripts/eval_dpo_contract_gate.py" --dataset "${DPO_JSON}"
  fi
else
  echo "DPO pipeline skipped (not enough preference pairs yet)."
fi

echo ""
echo "== 2/5 Create + validate finetune job =="
python3 <<PY
import json
import os
import sys

sys.path.insert(0, "$ROOT")
from app.state import get_finetune_service

service = get_finetune_service()
job = service.create_job(
    name="$DATASET_NAME",
    dataset_path="$DATASET_PATH",
    sample_count=int("$SAMPLE_COUNT"),
    base_model=os.getenv("TERMIT_STAGE1_BASE_MODEL", "ollama:qwen2.5-coder:14b"),
    notes="training_loop_week2.sh",
)
completed = service.run_job(job.job_id)
payload: dict[str, object] = {
    "job_id": completed.job_id,
    "status": completed.status,
    "train": None,
}
auto_train = os.getenv("TERMIT_FINETUNE_AUTO_TRAIN", "false").lower() in {"1", "true", "yes"}
if auto_train:
    output_model = os.getenv("TERMIT_FINETUNE_OUTPUT_MODEL", "termit-core-ft")
    trainer_mode = os.getenv("TERMIT_FINETUNE_TRAINER", "ollama")
    auto_register = os.getenv("TERMIT_FINETUNE_AUTO_REGISTER_AFTER_TRAIN", "false").lower() in {
        "1",
        "true",
        "yes",
    }
    repo_profile = os.getenv("TERMIT_FINETUNE_REPO_PROFILE_ID", "termit-core")
    train_result = service.train_job(
        completed.job_id,
        output_model=output_model,
        trainer_mode=trainer_mode,
        auto_register_adapter=auto_register,
        adapter_name="${DATASET_NAME}-ft",
        adapter_model=f"ollama:{output_model}",
        repo_profile_id=repo_profile,
    )
    payload["train"] = train_result
print(json.dumps(payload, indent=2))
if auto_train and isinstance(payload.get("train"), dict):
    status = str(payload["train"].get("status", ""))
    if status not in {"completed", "skipped"}:
        sys.exit(1)
PY

echo ""
echo "== 3/4 Training dashboard (signals, eval trend, tuning) =="
if curl -sf --max-time 5 "$BASE_URL/health" >/dev/null 2>&1; then
  curl -sf "$BASE_URL/api/finetune/training/dashboard?limit=5" | python3 -m json.tool | head -60
  echo ""
  echo "== 4/4 Agent tool-loop metrics =="
  curl -sf "$BASE_URL/api/ops/agent-runs/metrics" | python3 -m json.tool | head -25
else
  echo "Server not running on $BASE_URL — skip HTTP KPI (start uvicorn on :8765)."
fi

echo ""
echo "OK — training loop week2 complete."
