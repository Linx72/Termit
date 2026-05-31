import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional


class FeedbackStore:
    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path).resolve()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def append(
        self,
        message: str,
        rating: Optional[int],
        contact: Optional[str],
        api_key: Optional[str],
        *,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        instruction: Optional[str] = None,
    ) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "rating": rating,
            "contact": contact,
            "api_key": api_key,
        }
        if session_id:
            entry["session_id"] = session_id
        if task_id:
            entry["task_id"] = task_id
        if run_id:
            entry["run_id"] = run_id
        if instruction:
            entry["instruction"] = instruction
        line = json.dumps(entry, ensure_ascii=True)
        with self._lock:
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return entry["timestamp"]
