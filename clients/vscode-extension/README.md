# Termit VS Code Extension

**Termit in the editor** — sidebar with Chat, **Composer**, Tasks, Agents, and `apply_patch` with diff preview.

## Features

| Tab | Description |
|-----|-------------|
| **Chat** | Streaming, session memory, @ file, model picker, retrieval |
| **Composer** | Multi-file context → AI plan → parse patches → diff preview → apply all |
| **Tasks** | Background task queue and status |
| **Agents** | Agent profiles, run enqueue, **run list + event timeline** |

## Composer workflow

1. Open **Composer** tab (or `Termit: Open Composer`).
2. **@ add file** — attach workspace files as context (from active editor).
3. Describe the change (e.g. “Add retry to all HTTP clients in `app/`”).
4. **Run Composer** — Termit returns text + JSON patches.
5. **Double-click** a patch row → VS Code diff preview.
6. **Apply all patches** — writes via `POST /api/tools/apply_patch` (operator key if auth on).

## Commands

| Command | Description |
|---------|-------------|
| `Termit: Open Sidebar` | Chat tab |
| `Termit: Open Composer` | Composer tab |
| `Termit: Inline Edit (selection)` | Cmd+Alt+K inline edit on selection |
| `Termit: Create Task From Selection` | Queue task with selection |
| `Termit: Add Selection To Chat` | Append editor context |
| `Termit: Apply Patch (with diff preview)` | Manual single-file patch |
| `Termit: Apply Patch From Clipboard JSON` | Paste patch JSON |
| `Termit: Check API Connection` | Provider health |

## Development

```bash
cd ../termit-client && npm install && npm run build
cd ../vscode-extension && npm install && npm run build
```

Press **F5** with this folder open.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `termit.baseUrl` | `http://127.0.0.1:8765` | Termit API |
| `termit.apiKey` | empty | `X-API-Key` (operator for patches) |
| `termit.includeEditorContext` | `true` | Auto context in chat |

See also [`../CLIENT_UX.md`](../CLIENT_UX.md).

## Inline edit (Cmd+Alt+K)

1. Select code in the editor.
2. Run **Termit: Inline Edit (selection)** or `Cmd+Alt+K`.
3. Enter an instruction (e.g. “add error handling”).
4. Review diff preview and confirm apply.

## Tab completion

Ghost-text suggestions while typing (off by default):

| Setting | Default | Description |
|---------|---------|-------------|
| `termit.inlineCompletion.enabled` | `false` | Enable inline completion provider |
| `termit.inlineCompletion.debounceMs` | `400` | Debounce before requesting completion |

## Agent timeline

In the **Agents** tab: click an agent to list recent runs; click a run to watch tool-loop events via **SSE** (`watchAgentRun` / `GET /api/agents/runs/{id}/stream`).
