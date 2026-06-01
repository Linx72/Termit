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
echo "== 2/4 Create + validate finetune job (dry run) =="
python3 <<PY
import json
from pathlib import Path
import sys
sys.path.insert(0, "$ROOT")
from app.core.config import get_settings
from app.services.finetune_service import FinetuneService

settings = get_settings()
service = FinetuneService(
    datasets_dir=settings.finetune_datasets_dir,
    jobs_path=settings.finetune_jobs_path,
    adapters_path=settings.finetune_adapters_path,
    feedback_file_path=settings.feedback_file_path,
    task_sqlite_path=settings.task_sqlite_path,
    agent_run_sqlite_path=settings.agent_run_sqlite_path,
    repo_profiles_path=settings.repo_model_profiles_path,
    memory_sqlite_path=settings.memory_sqlite_path,
    eval_report_file_path=settings.eval_report_file_path,
    training_signals_path=settings.finetune_training_signals_path,
)
job = service.create_job(
    name="$DATASET_NAME",
    dataset_path="$DATASET_PATH",
    sample_count=int("$SAMPLE_COUNT"),
    base_model="ollama:deepseek-coder",
    notes="training_loop_week2.sh",
)
completed = service.run_job(job.job_id)
print(json.dumps({"job_id": completed.job_id, "status": completed.status}, indent=2))
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
