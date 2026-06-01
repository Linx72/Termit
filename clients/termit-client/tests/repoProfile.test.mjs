import assert from "node:assert/strict";
import { test } from "node:test";
import {
  buildAgentRunScope,
  inferRepoProfileId,
  inferRetrievalPathPrefix,
  resolvedAgentModel,
} from "../dist/repoProfile.js";

test("inferRetrievalPathPrefix maps app workspace", () => {
  assert.equal(
    inferRetrievalPathPrefix("/Users/me/Projects/Termit/app/services"),
    "app/"
  );
});

test("inferRepoProfileId resolves termit-core from app prefix", () => {
  assert.equal(inferRepoProfileId("app/services/agent_service.py"), "termit-core");
  assert.equal(inferRepoProfileId("tests/test_foo.py"), "termit-tests");
});

test("buildAgentRunScope includes workspace and profile", () => {
  const scope = buildAgentRunScope({
    workspace: "/repo/Termit/app",
    repoProfile: "",
  });
  assert.equal(scope.retrieval_path_prefix, "app/");
  assert.equal(scope.repo_profile, "termit-core");
  assert.match(scope.workspace_scope ?? "", /Termit\/app/);
});

test("resolvedAgentModel prefers attempted_models", () => {
  assert.equal(
    resolvedAgentModel({
      model: "fallback",
      attempted_models: ["ollama:termit-core-ft"],
    }),
    "ollama:termit-core-ft"
  );
});
