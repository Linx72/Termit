from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional


class TrainingSignalStore:
    """Append-only capture of high-quality task/agent outputs for finetune export."""

    def __init__(
        self,
        file_path: str = "./data/finetune/training_signals.jsonl",
        *,
        min_output_chars: int = 32,
        enabled: bool = True,
    ) -> None:
        self.file_path = Path(file_path).resolve()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._min_output_chars = max(8, min_output_chars)
        self._enabled = enabled
        self._lock = Lock()
        self._known_ids: Optional[set[str]] = None

    def try_capture_agent_run(
        self,
        *,
        run_id: str,
        instruction: str,
        response: str,
        session_id: Optional[str] = None,
        trajectory: str = "",
        category: str = "agent",
    ) -> bool:
        if not self._enabled:
            return False
        output = response.strip()
        prompt = instruction.strip()
        if len(output) < self._min_output_chars or len(prompt) < 4:
            return False
        signal_id = f"run:{run_id}"
        if self._has_signal(signal_id):
            return False
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_id": signal_id,
            "source": "training_signal",
            "origin": "agent_run",
            "instruction": prompt,
            "input": trajectory.strip(),
            "output": output,
            "category": category,
            "run_id": run_id,
        }
        if session_id:
            row["session_id"] = session_id
        return self._append(row)

    def try_capture_task(
        self,
        *,
        task_id: str,
        instruction: str,
        report: str,
        task_type: str = "general",
        session_id: Optional[str] = None,
        trajectory: str = "",
    ) -> bool:
        if not self._enabled:
            return False
        output = report.strip()
        prompt = instruction.strip()
        if len(output) < self._min_output_chars or len(prompt) < 4:
            return False
        signal_id = f"task:{task_id}"
        if self._has_signal(signal_id):
            return False
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_id": signal_id,
            "source": "training_signal",
            "origin": "task",
            "instruction": prompt,
            "input": trajectory.strip(),
            "output": output,
            "category": task_type,
            "task_id": task_id,
        }
        if session_id:
            row["session_id"] = session_id
        return self._append(row)

    def load_samples(self, limit: int = 500) -> list[dict[str, str]]:
        if not self.file_path.exists():
            return []
        safe_limit = max(1, min(limit, 5000))
        rows: list[dict[str, str]] = []
        with self._lock:
            lines = self.file_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            if len(rows) >= safe_limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            instruction = str(item.get("instruction", "")).strip()
            output = str(item.get("output", "")).strip()
            if len(instruction) < 4 or len(output) < self._min_output_chars:
                continue
            sample: dict[str, str] = {
                "instruction": instruction,
                "input": str(item.get("input", "")).strip(),
                "output": output,
                "source": "training_signal",
                "category": str(item.get("category", "general") or "general"),
            }
            for key in ("run_id", "task_id", "session_id", "signal_id"):
                value = item.get(key)
                if value:
                    sample[key] = str(value)
            rows.append(sample)
        rows.reverse()
        return rows

    def _append(self, row: dict[str, object]) -> bool:
        line = json.dumps(row, ensure_ascii=False)
        with self._lock:
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            if self._known_ids is not None:
                self._known_ids.add(str(row["signal_id"]))
        return True

    def _has_signal(self, signal_id: str) -> bool:
        with self._lock:
            if self._known_ids is None:
                self._known_ids = set()
                if self.file_path.exists():
                    for line in self.file_path.read_text(encoding="utf-8").splitlines():
                        if not line.strip():
                            continue
                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        value = item.get("signal_id")
                        if value:
                            self._known_ids.add(str(value))
            return signal_id in self._known_ids
