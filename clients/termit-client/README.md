# @termit/client

TypeScript client for the [Termit](https://github.com/) AI coding orchestrator API.

## Install

```bash
cd clients/termit-client
npm install
npm run build
```

From another project:

```bash
npm install ../termit-client
```

## Usage

```typescript
import { TermitClient } from "@termit/client";

const client = new TermitClient({
  baseUrl: "http://127.0.0.1:8765",
  apiKey: process.env.TERMIT_API_KEY,
});

// Non-streaming chat
const reply = await client.chat({
  message: "Explain this repo structure",
  task_type: "explain",
});
console.log(reply.response);

// Streaming chat (SSE: meta → token → done)
for await (const event of client.chatStream({ message: "Hello" })) {
  if (event.event === "meta") {
    console.log("model:", event.data.model);
  } else if (event.event === "token") {
    process.stdout.write(String(event.data.text ?? ""));
  }
}

// Background task
const task = await client.createTask({
  input: "Add unit tests for model router",
  task_type: "coding",
});

// Apply a patch (requires confirmed=true for writes)
await client.applyPatch({
  path: "app/example.py",
  hunks: [{ old_text: "old", new_text: "new" }],
  confirmed: true,
});

// Tools
const files = await client.listFiles({ path: ".", pattern: "*.py" });
const source = await client.readFile({ path: "README.md" });
```

## API coverage

- `chat`, `chatStream`
- `createTask`, `getTask`, `listTasks`
- `listAgents`, `createAgentRun`, `getAgentRun`, `getAgentRunEvents`, `agentRunStream`
- `applyPatch`, `readFile`, `listFiles`, `executeCommand`

## Workflows (shared by VS Code + desktop)

- `watchAgentRun` — SSE status stream + event refresh
- `fetchInlineEditPatch` — Cmd+K inline edit
- `requestTabCompletion` — ghost-text completion prompt
- `computePatchedContent`, `formatAgentTimeline`
- Composer helpers: `buildComposerMessage`, `parseComposerPatches`, `pickInlinePatch`
