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
    ) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message,
            "rating": rating,
            "contact": contact,
            "api_key": api_key,
        }
        line = json.dumps(entry, ensure_ascii=True)
        with self._lock:
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return entry["timestamp"]
