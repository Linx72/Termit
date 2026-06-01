import assert from "node:assert/strict";
import { test } from "node:test";
import { TermitAgent } from "../dist/agent.js";

test("TermitAgent.resume calls resume endpoint for failed runs", async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url: String(url), method: init?.method ?? "GET" });
    if (String(url).endsWith("/resume") && init?.method === "POST") {
      return {
        ok: true,
        status: 200,
        json: async () => ({ run_id: "r1", state: "queued", resumed: true }),
      };
    }
    if (String(url).includes("/api/agents/runs/r1")) {
      const resumed = calls.some((item) => item.url.endsWith("/resume"));
      return {
        ok: true,
        status: 200,
        json: async () => ({
          run_id: "r1",
          agent_id: "agent-1",
          agent_name: "Coder",
          state: resumed ? "queued" : "failed",
          created_at: "t0",
          updated_at: "t1",
          input: "fix bug",
        }),
      };
    }
    throw new Error(`unexpected fetch: ${url}`);
  };

  const agent = await TermitAgent.resume("r1", { baseUrl: "http://127.0.0.1:8765", fetchImpl });
  assert.equal(agent.agentId, "agent-1");
  assert.ok(calls.some((item) => item.url.endsWith("/resume") && item.method === "POST"));
});

test("TermitAgent.resume skips resume for completed runs", async () => {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url: String(url), method: init?.method ?? "GET" });
    if (String(url).includes("/api/agents/runs/r2")) {
      return {
        ok: true,
        status: 200,
        json: async () => ({
          run_id: "r2",
          agent_id: "agent-2",
          agent_name: "Coder",
          state: "completed",
          created_at: "t0",
          updated_at: "t1",
          input: "done",
        }),
      };
    }
    throw new Error(`unexpected fetch: ${url}`);
  };

  const agent = await TermitAgent.resume("r2", { baseUrl: "http://127.0.0.1:8765", fetchImpl });
  assert.equal(agent.agentId, "agent-2");
  assert.equal(calls.filter((item) => item.url.endsWith("/resume")).length, 0);
});
