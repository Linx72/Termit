from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4


class CrossPlatformPlanStore:
    """JSONL store for resumable cross-platform decomposition plans."""

    def __init__(self, file_path: str = "./data/cross_platform_plans.jsonl") -> None:
        self.file_path = Path(file_path).resolve()
        self._lock = Lock()

    def save_plan(
        self,
        *,
        goal: str,
        stack_id: str,
        platforms: list[str],
        atomic_tasks: list[dict[str, object]],
    ) -> str:
        plan_id = f"cp_{uuid4().hex[:12]}"
        row = {
            "plan_id": plan_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "goal": goal,
            "stack_id": stack_id,
            "platforms": platforms,
            "atomic_tasks": atomic_tasks,
            "completed_step_ids": [],
        }
        with self._lock:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return plan_id

    def get_plan(self, plan_id: str) -> dict[str, object] | None:
        if not self.file_path.exists():
            return None
        latest: dict[str, object] | None = None
        with self._lock:
            for line in self.file_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(row.get("plan_id")) == plan_id:
                    latest = row
        return latest

    def mark_step_completed(self, plan_id: str, step_id: str) -> bool:
        plan = self.get_plan(plan_id)
        if plan is None:
            return False
        completed = [str(item) for item in plan.get("completed_step_ids") or []]
        if step_id not in completed:
            completed.append(step_id)
        plan["completed_step_ids"] = completed
        with self._lock:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(plan, ensure_ascii=False) + "\n")
        return True
