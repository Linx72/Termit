"""Tests for structured agent activity event payloads."""

from __future__ import annotations

import json

from app.services.agent_activity_events import (
    activity_summary_from_events,
    count_line_diff,
    events_for_loop_step,
    file_edit_from_patch_observation,
)


def test_count_line_diff_insert_and_delete() -> None:
    added, removed = count_line_diff("a\nb\n", "a\nc\n")
    assert added == 1
    assert removed == 1


def test_file_edit_from_patch_observation_applied() -> None:
    observation = json.dumps(
        {
            "patch": {
                "path": "src/main.py",
                "applied": True,
                "created": False,
                "lines_added": 3,
                "lines_removed": 1,
                "hunks_applied": 1,
            }
        }
    )
    payload = file_edit_from_patch_observation(observation)
    assert payload is not None
    assert payload["kind"] == "file_edit"
    assert payload["path"] == "src/main.py"
    assert payload["lines_added"] == 3
    assert payload["lines_removed"] == 1
    assert payload["pending"] is False


def test_events_for_loop_step_apply_patch() -> None:
    observation = json.dumps(
        {
            "patch": {
                "path": "README.md",
                "applied": True,
                "created": True,
                "lines_added": 10,
                "lines_removed": 0,
            }
        }
    )
    emitted = events_for_loop_step(
        tool="apply_patch",
        observation=observation,
        step_message="Step 2: tool (apply_patch)",
    )
    assert len(emitted) == 2
    assert emitted[0][0] == "tool_activity"
    assert emitted[1][0] == "file_edit_completed"
    assert emitted[1][2]["operation"] == "create"


def test_activity_summary_from_events() -> None:
    events = [
        {
            "payload": {
                "kind": "file_edit",
                "path": "a.ts",
                "lines_added": 2,
                "lines_removed": 1,
                "pending": False,
            }
        },
        {
            "payload": {
                "kind": "file_edit",
                "path": "b.ts",
                "lines_added": 5,
                "lines_removed": 0,
                "pending": True,
            }
        },
    ]
    summary = activity_summary_from_events(events, in_progress=True)
    assert summary["kind"] == "activity_summary"
    assert summary["files_count"] == 2
    assert summary["lines_added"] == 7
    assert summary["lines_removed"] == 1
    assert summary["in_progress"] is True
