from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.services.training_signal_store import TrainingSignalStore


@dataclass(frozen=True)
class AppliedPatchRecord:
    run_id: str
    path: str
    content_hash: str
    instruction: str
    captured_at: str
    chosen_patch: str = ""


class PatchOutcomeStore:
    """Track agent-applied patches and detect user edits/reverts for DPO signals."""

    def __init__(
        self,
        file_path: str = "./data/finetune/patch_outcomes.jsonl",
        *,
        enabled: bool = True,
        max_pending_per_path: int = 8,
    ) -> None:
        self.file_path = Path(file_path).resolve()
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._enabled = enabled
        self._max_pending = max(1, max_pending_per_path)
        self._lock = Lock()

    @staticmethod
    def file_hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def record_applied_patch(
        self,
        *,
        run_id: str,
        rel_path: str,
        root_path: str,
        instruction: str = "",
        chosen_patch: str = "",
    ) -> bool:
        if not self._enabled:
            return False
        normalized = rel_path.replace("\\", "/").strip()
        if not normalized or not run_id:
            return False
        target = Path(root_path).resolve() / normalized
        if not target.exists() or not target.is_file():
            return False
        try:
            content_hash = self.file_hash(target)
        except OSError:
            return False
        row = {
            "event": "applied",
            "run_id": run_id,
            "path": normalized,
            "content_hash": content_hash,
            "instruction": instruction.strip()[:2000],
            "chosen_patch": chosen_patch.strip()[:4000],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True

    def handle_file_changed(
        self,
        rel_path: str,
        *,
        root_path: str,
        training_signals: Optional["TrainingSignalStore"] = None,
    ) -> bool:
        if not self._enabled:
            return False
        normalized = rel_path.replace("\\", "/").strip()
        if not normalized:
            return False
        target = Path(root_path).resolve() / normalized
        if not target.exists() or not target.is_file():
            return self._mark_resolved(normalized, reason="missing")

        try:
            current_hash = self.file_hash(target)
        except OSError:
            return False

        pending = self._pending_for_path(normalized)
        if not pending:
            return False

        captured = False
        for record in pending:
            if record.content_hash == current_hash:
                continue
            if training_signals is not None:
                captured = training_signals.try_capture_patch_revert(
                    run_id=record.run_id,
                    path=normalized,
                    instruction=record.instruction,
                    original_hash=record.content_hash,
                    new_hash=current_hash,
                    chosen_output=record.chosen_patch,
                ) or captured
            self._append_event(
                {
                    "event": "reverted",
                    "run_id": record.run_id,
                    "path": normalized,
                    "original_hash": record.content_hash,
                    "new_hash": current_hash,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        return captured

    def scan_git_worktree(
        self,
        root_path: str,
        *,
        training_signals: Optional["TrainingSignalStore"] = None,
    ) -> int:
        """Proactively detect git reverts and file edits for pending agent patches."""
        root = Path(root_path).resolve()
        captured = 0
        pending_paths = self._pending_paths()
        for rel_path in pending_paths:
            if self.handle_file_changed(
                rel_path,
                root_path=str(root),
                training_signals=training_signals,
            ):
                captured += 1
                continue
            if not (root / ".git").is_dir():
                continue
            if self._capture_git_head_revert(
                rel_path,
                root=root,
                training_signals=training_signals,
            ):
                captured += 1
        return captured

    def _pending_paths(self) -> list[str]:
        if not self.file_path.exists():
            return []
        paths: set[str] = set()
        with self._lock:
            lines = self.file_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(item.get("event", "")) == "applied":
                path = str(item.get("path", "")).strip()
                if path:
                    paths.add(path)
        return sorted(paths)

    def _git_head_file_hash(self, root: Path, rel_path: str) -> Optional[str]:
        try:
            completed = subprocess.run(
                ["git", "-C", str(root), "show", f"HEAD:{rel_path}"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0:
            return None
        return hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest()

    def _capture_git_head_revert(
        self,
        rel_path: str,
        *,
        root: Path,
        training_signals: Optional["TrainingSignalStore"],
    ) -> bool:
        target = root / rel_path
        if not target.exists() or not target.is_file():
            return False
        try:
            current_hash = self.file_hash(target)
        except OSError:
            return False
        head_hash = self._git_head_file_hash(root, rel_path)
        if not head_hash or head_hash != current_hash:
            return False

        pending = self._pending_for_path(rel_path)
        captured = False
        for record in pending:
            if record.content_hash == current_hash:
                continue
            if training_signals is not None:
                captured = training_signals.try_capture_patch_revert(
                    run_id=record.run_id,
                    path=rel_path,
                    instruction=record.instruction,
                    original_hash=record.content_hash,
                    new_hash=current_hash,
                    chosen_output=record.chosen_patch,
                ) or captured
            self._append_event(
                {
                    "event": "reverted",
                    "run_id": record.run_id,
                    "path": rel_path,
                    "original_hash": record.content_hash,
                    "new_hash": current_hash,
                    "source": "git_head",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        return captured

    def _pending_for_path(self, path: str) -> list[AppliedPatchRecord]:
        if not self.file_path.exists():
            return []
        resolved_run_ids: set[str] = set()
        with self._lock:
            lines = self.file_path.read_text(encoding="utf-8").splitlines()
        pending: list[AppliedPatchRecord] = []
        for line in reversed(lines):
            if len(pending) >= self._max_pending:
                break
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(item.get("path", "")) != path:
                continue
            event = str(item.get("event", ""))
            run_id = str(item.get("run_id", ""))
            if not run_id:
                continue
            if event == "reverted":
                resolved_run_ids.add(run_id)
                continue
            if event != "applied" or run_id in resolved_run_ids:
                continue
            pending.append(
                AppliedPatchRecord(
                    run_id=run_id,
                    path=path,
                    content_hash=str(item.get("content_hash", "")),
                    instruction=str(item.get("instruction", "")),
                    captured_at=str(item.get("timestamp", "")),
                    chosen_patch=str(item.get("chosen_patch", "")),
                )
            )
        return pending

    def _mark_resolved(self, path: str, *, reason: str) -> bool:
        self._append_event(
            {
                "event": "reverted",
                "run_id": "",
                "path": path,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return False

    def _append_event(self, row: dict[str, object]) -> None:
        with self._lock:
            with self.file_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
