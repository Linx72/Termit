import assert from "node:assert/strict";
import { test } from "node:test";
import {
  buildTabCompletionMessage,
  formatAgentTimeline,
  parseTabCompletionResponse,
} from "../dist/workflows.js";

test("formatAgentTimeline includes run and events", () => {
  const text = formatAgentTimeline(
    {
      run_id: "r1",
      agent_id: "a1",
      agent_name: "Agent",
      state: "running",
      created_at: "t0",
      updated_at: "t1",
      input: "hello",
    },
    [{ event_type: "tool_start", state: "running", message: "read_file", timestamp: "t2" }]
  );
  assert.match(text, /r1/);
  assert.match(text, /tool_start/);
});

test("parseTabCompletionResponse rejects empty or multiline blocks", () => {
  assert.equal(parseTabCompletionResponse(""), undefined);
  assert.equal(parseTabCompletionResponse("line1\n\nline2"), undefined);
  assert.equal(parseTabCompletionResponse("  foo  "), "foo");
});

test("buildTabCompletionMessage includes before and after", () => {
  const message = buildTabCompletionMessage("before", "after");
  assert.match(message, /before/);
  assert.match(message, /after/);
});
