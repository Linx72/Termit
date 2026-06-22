import assert from "node:assert/strict";
import test from "node:test";
import {
  reduceAgentActivity,
  reduceAgentActivityWithFallback,
  shouldShowLineStats,
  formatActivitySummaryLabel,
} from "../dist/activity.js";

test("reduceAgentActivity aggregates file edits", () => {
  const state = reduceAgentActivity(
    [
      {
        event_type: "file_edit_completed",
        state: "running",
        message: "edit a.ts",
        timestamp: "2026-01-01T00:00:00Z",
        payload: {
          kind: "file_edit",
          path: "src/a.ts",
          operation: "edit",
          lines_added: 4,
          lines_removed: 1,
          pending: false,
        },
      },
    ],
    { run: { state: "running" }, locale: "en" }
  );
  assert.equal(state.fileEdits.length, 1);
  assert.equal(state.summary.linesAdded, 4);
  assert.match(state.summary.label, /Agent is working/);
});

test("reduceAgentActivityWithFallback uses git changes when no structured edits", () => {
  const state = reduceAgentActivityWithFallback([], {
    gitFallback: [{ path: "README.md", status: "M" }],
    locale: "en",
  });
  assert.equal(state.fileEdits.length, 1);
  assert.equal(state.fileEdits[0].path, "README.md");
});

test("shouldShowLineStats respects detail level", () => {
  assert.equal(shouldShowLineStats("compact"), false);
  assert.equal(shouldShowLineStats("detailed"), true);
});

test("formatActivitySummaryLabel localized", () => {
  assert.match(
    formatActivitySummaryLabel("ru", {
      filesCount: 2,
      linesAdded: 3,
      linesRemoved: 1,
      inProgress: true,
    }),
    /файлов/
  );
});
