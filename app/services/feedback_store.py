import json
from datetime import datetime, timedelta, timezone
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

    def list_entries(self, *, limit: int = 500) -> list[dict[str, object]]:
        if not self.file_path.is_file():
            return []
        safe_limit = max(1, min(limit, 5000))
        with self._lock:
            lines = self.file_path.read_text(encoding="utf-8").splitlines()
        entries: list[dict[str, object]] = []
        for line in reversed(lines):
            if len(entries) >= safe_limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
        return list(reversed(entries))

    def summarize(self) -> dict[str, object]:
        entries = self.list_entries(limit=5000)
        if not entries:
            return {
                "total": 0,
                "recent_7d": 0,
                "avg_rating": None,
                "rating_counts": {},
            }
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_7d = 0
        ratings: list[int] = []
        rating_counts: dict[str, int] = {}
        for entry in entries:
            ts_raw = str(entry.get("timestamp", ""))
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                if ts >= week_ago:
                    recent_7d += 1
            except ValueError:
                pass
            rating = entry.get("rating")
            if isinstance(rating, int):
                ratings.append(rating)
                key = str(rating)
                rating_counts[key] = rating_counts.get(key, 0) + 1
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
        return {
            "total": len(entries),
            "recent_7d": recent_7d,
            "avg_rating": avg_rating,
            "rating_counts": rating_counts,
        }
