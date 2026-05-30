from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


class EvalReportStore:
    def __init__(self, file_path: str = "./data/eval_reports.jsonl") -> None:
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def append_suite_report(self, report: dict[str, object]) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = {"timestamp": timestamp, **report}
        line = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return timestamp

    def list_recent(self, limit: int = 10) -> list[dict[str, object]]:
        safe_limit = max(1, min(limit, 100))
        if not self.file_path.exists():
            return []
        with self._lock:
            lines = self.file_path.read_text(encoding="utf-8").splitlines()
        reports: list[dict[str, object]] = []
        for line in lines[-safe_limit:]:
            line = line.strip()
            if not line:
                continue
            reports.append(json.loads(line))
        reports.reverse()
        return reports
