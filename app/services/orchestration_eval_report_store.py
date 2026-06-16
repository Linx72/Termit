from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


class OrchestrationEvalReportStore:
    def __init__(self, file_path: str = "./data/orchestration_eval_reports.jsonl") -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def append_report(self, report: dict[str, object]) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = {"timestamp": timestamp, **report}
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return timestamp

    def list_recent(self, limit: int = 20) -> list[dict[str, object]]:
        safe_limit = max(1, min(limit, 200))
        if not self.file_path.exists():
            return []
        with self._lock:
            lines = self.file_path.read_text(encoding="utf-8").splitlines()
        items: list[dict[str, object]] = []
        for line in lines[-safe_limit:]:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
        items.reverse()
        return items

    def trend_points(self, limit: int = 24) -> list[dict[str, object]]:
        points: list[dict[str, object]] = []
        for item in self.list_recent(limit=limit):
            metrics_after = item.get("metrics_after", {})
            retry_success = 0.0
            if isinstance(metrics_after, dict):
                retry_success = float(metrics_after.get("coder_retry_success_rate", 0.0) or 0.0)
            points.append(
                {
                    "captured_at": str(item.get("timestamp", "")),
                    "pass_rate": float(item.get("pass_rate", 0.0) or 0.0),
                    "retry_success_rate": retry_success,
                    "total": int(item.get("total", 0) or 0),
                }
            )
        points.reverse()
        return points
