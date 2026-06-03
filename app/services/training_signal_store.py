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

    def try_capture_tool_step(
        self,
        *,
        run_id: str,
        step: int,
        action: str,
        tool: Optional[str] = None,
        observation: str = "",
        instruction: str = "",
        assistant_text: str = "",
        verified: bool = False,
    ) -> bool:
        """Capture high-value tool-loop steps (e.g. successful apply_patch) for SFT."""
        if not self._enabled:
            return False
        if action not in {"tool", "final"} and not verified:
            return False
        if tool not in {None, "", "apply_patch"} and not verified:
            return False
        observation_text = observation.strip()
        if verified and len(observation_text) < 8:
            return False
        if not verified and len(observation_text) < self._min_output_chars:
            return False
        signal_id = f"run:{run_id}:step:{step}"
        if self._has_signal(signal_id):
            return False
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_id": signal_id,
            "source": "training_signal",
            "origin": "tool_step",
            "instruction": instruction.strip(),
            "input": json.dumps(
                {
                    "step": step,
                    "action": action,
                    "tool": tool or "",
                    "observation": observation_text[:4000],
                    "assistant": assistant_text[:4000],
                },
                ensure_ascii=False,
            ),
            "output": observation_text[:8000] if verified else assistant_text[:8000],
            "category": "tool_loop",
            "run_id": run_id,
            "eval_passed": "1" if verified else "0",
        }
        return self._append(row)

    def try_capture_subagent_run(
        self,
        *,
        parent_run_id: str,
        child_run_id: str,
        task: str,
        success: bool,
        summary: str = "",
    ) -> bool:
        if not self._enabled:
            return False
        prompt = task.strip()
        output = summary.strip() or ("subagent run completed" if success else "subagent run failed")
        if len(output) < self._min_output_chars and len(prompt) >= 4:
            output = (output + " " + task).strip()[:8000]
        if len(prompt) < 4:
            return False
        signal_id = f"subagent:{parent_run_id}:{child_run_id}"
        if self._has_signal(signal_id):
            return False
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_id": signal_id,
            "source": "training_signal",
            "origin": "subagent_run",
            "instruction": prompt,
            "input": json.dumps(
                {"parent_run_id": parent_run_id, "child_run_id": child_run_id},
                ensure_ascii=False,
            ),
            "output": output[:8000] if output else ("completed" if success else "failed"),
            "category": "subagent",
            "run_id": child_run_id,
            "parent_run_id": parent_run_id,
            "eval_passed": "1" if success else "0",
        }
        return self._append(row)

    def try_capture_negative_tool_step(
        self,
        *,
        run_id: str,
        step: int,
        action: str,
        tool: Optional[str] = None,
        observation: str = "",
        instruction: str = "",
        reason: str = "verify_failed",
    ) -> bool:
        """Capture failed tool steps for DPO / negative SFT export."""
        if not self._enabled:
            return False
        observation_text = observation.strip()
        if len(observation_text) < 8 and len(instruction) < 4:
            return False
        signal_id = f"run:{run_id}:neg:step:{step}"
        if self._has_signal(signal_id):
            return False
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_id": signal_id,
            "source": "training_signal",
            "origin": "tool_step_negative",
            "instruction": instruction.strip(),
            "input": json.dumps(
                {
                    "step": step,
                    "action": action,
                    "tool": tool or "",
                    "observation": observation_text[:4000],
                    "reason": reason,
                },
                ensure_ascii=False,
            ),
            "output": observation_text[:8000],
            "rejected": observation_text[:8000],
            "category": "tool_loop_negative",
            "run_id": run_id,
            "eval_passed": "0",
            "skip_export": "0",
        }
        return self._append(row)

    def try_capture_patch_revert(
        self,
        *,
        run_id: str,
        path: str,
        instruction: str = "",
        original_hash: str = "",
        new_hash: str = "",
        chosen_output: str = "",
    ) -> bool:
        if not self._enabled:
            return False
        signal_id = f"run:{run_id}:revert:{path}"
        if self._has_signal(signal_id):
            return False
        detail = (
            f"User edited or reverted agent patch on {path}. "
            f"hash {original_hash[:12]} -> {new_hash[:12]}"
        )
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_id": signal_id,
            "source": "training_signal",
            "origin": "patch_revert",
            "instruction": instruction.strip() or f"Apply patch to {path}",
            "input": json.dumps(
                {"path": path, "original_hash": original_hash, "new_hash": new_hash},
                ensure_ascii=False,
            ),
            "output": detail,
            "rejected": detail,
            "category": "patch_revert",
            "run_id": run_id,
            "eval_passed": "0",
        }
        if chosen_output.strip():
            row["chosen"] = chosen_output.strip()[:8000]
        return self._append(row)

    def try_capture_cross_platform_step(
        self,
        *,
        goal: str,
        stack_id: str,
        step_id: str,
        step_index: int,
        verify_ok: bool,
        verify_detail: str = "",
        plan_id: Optional[str] = None,
    ) -> bool:
        if not self._enabled:
            return False
        signal_id = f"cross_platform:{stack_id}:{step_id}:{step_index}"
        if self._has_signal(signal_id):
            return False
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_id": signal_id,
            "source": "training_signal",
            "origin": "cross_platform_atomic",
            "instruction": goal.strip()[:4000],
            "input": f"stack={stack_id} step={step_id} index={step_index}",
            "output": verify_detail.strip()[:2000] or ("verify_ok" if verify_ok else "verify_failed"),
            "category": "cross_platform",
            "eval_passed": "1" if verify_ok else "0",
        }
        if plan_id:
            row["plan_id"] = plan_id
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
            origin = str(item.get("origin", ""))
            if origin:
                sample["origin"] = origin
            rejected = str(item.get("rejected", "")).strip()
            if rejected:
                sample["rejected"] = rejected
            rows.append(sample)
        rows.reverse()
        return rows

    def load_dpo_samples(self, limit: int = 500) -> list[dict[str, str]]:
        """Negative tool-step signals formatted for preference tuning export."""
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
            if str(item.get("origin", "")) not in {
                "tool_step_negative",
                "patch_revert",
            }:
                continue
            instruction = str(item.get("instruction", "")).strip()
            rejected = str(item.get("rejected", item.get("output", ""))).strip()
            if len(instruction) < 4 or len(rejected) < self._min_output_chars:
                continue
            sample = {
                "instruction": instruction,
                "input": str(item.get("input", "")).strip(),
                "output": rejected,
                "rejected": rejected,
                "source": "dpo_negative",
                "category": str(item.get("category", "tool_loop_negative")),
                "run_id": str(item.get("run_id", "")),
            }
            chosen = str(item.get("chosen", "")).strip()
            if chosen:
                sample["chosen"] = chosen
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
