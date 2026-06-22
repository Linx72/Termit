"""Structured activity payloads for agent run timeline events (file edits, tools)."""

from __future__ import annotations

import difflib
import json
from typing import Any


def count_line_diff(old_text: str, new_text: str) -> tuple[int, int]:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    added = 0
    removed = 0
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in {"insert", "replace"}:
            added += j2 - j1
        if tag in {"delete", "replace"}:
            removed += i2 - i1
    return added, removed


def file_edit_payload(
    *,
    path: str,
    operation: str,
    lines_added: int = 0,
    lines_removed: int = 0,
    pending: bool = False,
    tool: str = "apply_patch",
    hunks_applied: int = 0,
) -> dict[str, Any]:
    return {
        "kind": "file_edit",
        "path": path,
        "operation": operation,
        "lines_added": max(0, lines_added),
        "lines_removed": max(0, lines_removed),
        "pending": pending,
        "tool": tool,
        "hunks_applied": hunks_applied,
    }


def tool_activity_payload(*, tool: str, label: str, pending: bool = False) -> dict[str, Any]:
    return {
        "kind": "tool",
        "tool": tool,
        "label": label,
        "pending": pending,
    }


def activity_summary_payload(
    *,
    files_count: int,
    lines_added: int,
    lines_removed: int,
    in_progress: bool,
    label: str,
) -> dict[str, Any]:
    return {
        "kind": "activity_summary",
        "files_count": files_count,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "in_progress": in_progress,
        "label": label,
    }


def file_edit_from_patch_observation(observation: str) -> dict[str, Any] | None:
    try:
        data = json.loads(observation)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    patch = data.get("patch")
    if not isinstance(patch, dict) and data.get("path"):
        patch = data
    if not isinstance(patch, dict):
        return None
    path = str(patch.get("path", "")).strip()
    if not path:
        return None
    applied = bool(patch.get("applied"))
    created = bool(patch.get("created"))
    requires_confirmation = bool(patch.get("requires_confirmation"))
    operation = "create" if created else "edit"
    lines_added = int(patch.get("lines_added") or 0)
    lines_removed = int(patch.get("lines_removed") or 0)
    pending = requires_confirmation and not applied
    if not applied and not requires_confirmation and not patch.get("dry_run"):
        return None
    return file_edit_payload(
        path=path,
        operation=operation,
        lines_added=lines_added,
        lines_removed=lines_removed,
        pending=pending or (not applied and bool(patch.get("dry_run"))),
        hunks_applied=int(patch.get("hunks_applied") or 0),
    )


def events_for_loop_step(*, tool: str | None, observation: str, step_message: str) -> list[tuple[str, str, dict[str, Any] | None]]:
    """Return (event_type, message, payload) tuples for a completed loop step."""
    emitted: list[tuple[str, str, dict[str, Any] | None]] = []
    if not tool:
        return emitted

    emitted.append(
        (
            "tool_activity",
            step_message,
            tool_activity_payload(tool=tool, label=step_message, pending=False),
        )
    )

    if tool == "apply_patch":
        payload = file_edit_from_patch_observation(observation)
        if payload is not None:
            status = "progress" if payload.get("pending") else "completed"
            event_type = "file_edit_progress" if status == "progress" else "file_edit_completed"
            path = payload["path"]
            op = payload["operation"]
            la = payload["lines_added"]
            lr = payload["lines_removed"]
            message = f"{op} {path} (+{la} −{lr})" if not payload.get("pending") else f"Editing {path}…"
            emitted.append((event_type, message, payload))

    return emitted


def activity_summary_from_events(events: list[Any], *, in_progress: bool) -> dict[str, Any]:
    """Aggregate file-edit payloads from timeline events into a summary payload."""
    files: dict[str, dict[str, Any]] = {}
    for ev in events:
        payload = ev.get("payload") if isinstance(ev, dict) else getattr(ev, "payload", None)
        if not isinstance(payload, dict) or payload.get("kind") != "file_edit":
            continue
        path = str(payload.get("path", "")).strip()
        if not path:
            continue
        files[path] = payload

    lines_added = sum(int(item.get("lines_added") or 0) for item in files.values())
    lines_removed = sum(int(item.get("lines_removed") or 0) for item in files.values())
    files_count = len(files)
    pending = any(bool(item.get("pending")) for item in files.values())
    label = (
        f"{files_count} files · +{lines_added} −{lines_removed}"
        + (" · Agent is working…" if in_progress or pending else "")
    )
    return activity_summary_payload(
        files_count=files_count,
        lines_added=lines_added,
        lines_removed=lines_removed,
        in_progress=in_progress or pending,
        label=label,
    )
