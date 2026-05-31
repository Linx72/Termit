import assert from "node:assert/strict";
import { test } from "node:test";
import {
  buildComposerMessage,
  buildInlineEditMessage,
  parseComposerPatches,
  pickInlinePatch,
  stripComposerJsonBlock,
} from "../dist/composer.js";

test("buildComposerMessage includes instruction and files", () => {
  const message = buildComposerMessage("Fix auth", [
    { path: "app/auth.py", content: "def login(): pass" },
  ]);
  assert.match(message, /Fix auth/);
  assert.match(message, /app\/auth\.py/);
  assert.match(message, /```json/);
});

test("parseComposerPatches reads patches array", () => {
  const text = `Here is the plan.

\`\`\`json
{"patches":[{"path":"a.py","hunks":[{"old_text":"foo","new_text":"bar"}]}]}
\`\`\``;
  const patches = parseComposerPatches(text);
  assert.equal(patches.length, 1);
  assert.equal(patches[0].path, "a.py");
  assert.equal(patches[0].hunks?.[0].new_text, "bar");
});

test("stripComposerJsonBlock removes fenced json", () => {
  const text = "Summary\n\n```json\n{}\n```";
  assert.equal(stripComposerJsonBlock(text), "Summary");
});

test("buildInlineEditMessage includes selection context", () => {
  const message = buildInlineEditMessage("Add logging", "src/a.ts", "typescript", "const x = 1;");
  assert.match(message, /Add logging/);
  assert.match(message, /src\/a\.ts/);
  assert.match(message, /const x = 1;/);
});

test("pickInlinePatch prefers exact hunk match", () => {
  const patches = [
    { path: "a.py", hunks: [{ old_text: "foo", new_text: "bar" }] },
    { path: "b.py", hunks: [{ old_text: "x", new_text: "y" }] },
  ];
  const picked = pickInlinePatch(patches, "a.py", "foo");
  assert.equal(picked?.path, "a.py");
});
