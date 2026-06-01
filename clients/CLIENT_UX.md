# Termit clients — Cursor-like UX, Termit AI

Termit clients copy **workflow and interface patterns** from Cursor-style coding assistants.  
They do **not** use Cursor's AI, billing, or `@cursor/sdk`.

```text
┌─────────────────────────────────────────┐
│  Client (desktop / VS Code)             │
│  Chat · Composer · @context · diff apply │  ← Cursor-like UX
└──────────────────┬──────────────────────┘
                   │ HTTP / SSE
┌──────────────────▼──────────────────────┐
│  Termit API (:8765)                     │
│  routing · Ollama · apply_patch · agents│  ← your AI stack
└─────────────────────────────────────────┘
```

## Feature map

| Cursor-style capability | Termit client | API |
|-------------------------|---------------|-----|
| Sidebar chat + streaming | Desktop + VS Code | `POST /api/chat/stream` |
| **Composer (multi-file)** | **Desktop + VS Code** | chat + JSON patches + `apply_patch` |
| Session memory | Both | `session_id` |
| @ file context | `@ file` buttons; Editor tab | `read_file`, editor context |
| @ folder / @ symbol | Desktop chat `@ folder`, `@ symbol` | `list_files`, `/api/retrieval/symbols/search` |
| @ docs / @ web | Desktop `@ docs`, `@ web` | `read_file`, `POST /api/platform/search` |
| @ codebase | Retrieval checkbox | `use_retrieval` |
| Plan mode | Desktop **Plan** tab → Build → Composer | chat stream (plan-only prompt) |
| Terminal | Desktop **Terminal** tab | `execute_command` |
| Health / queue / index | Desktop sidebar | `/api/ops/*`, `/api/retrieval/stats` |
| Model pull (Ollama) | Wizard + sidebar Model manager | `POST /api/local/models/pull` |
| Model picker | Both (after Connect) | `GET /api/providers` |
| Task queue | Both | `POST /api/tasks` |
| Custom agents | Both | `POST /api/agents/{id}/runs` |
| Apply edits with diff | VS Code Composer + patch cmd; Desktop Editor | `apply_patch` + diff preview |
| Apply all (batch) | Composer tab | multiple `apply_patch` |
| **Cmd+K inline edit** | **VS Code** (`Cmd+Alt+K`) + **Desktop Editor** (`Cmd+K`) | chat + single patch + diff |
| **Tab completion** | **VS Code + Desktop Editor** | `requestTabCompletion` |
| **Agent run timeline** | **Desktop + VS Code** | SSE `GET /api/agents/runs/{id}/stream` + events |

## Inline edit (VS Code)

1. Select code in editor.
2. `Cmd+Alt+K` (or context menu) → instruction prompt.
3. Termit returns JSON patch for the selection.
4. Diff preview → apply via `apply_patch`.

Enable ghost-text completion: `termit.inlineCompletion.enabled` (default off).

## Editor (desktop)

Monaco editor tab in the desktop app:

1. Choose workspace folder, connect, open **Editor** tab.
2. **Open file** — loads via `read_file`.
3. Select code → **Cmd+K** (or Inline edit button) → instruction prompt.
4. Termit returns JSON patch → side-by-side diff preview → **Apply patch** via `apply_patch`.
5. **Save** writes full file content through `apply_patch`.

## Agent timeline

After enqueue or when selecting a run, clients stream run status via SSE and refresh tool-loop events on each status change until a terminal state (`completed`, `failed`, `cancelled`).

Enable ghost-text completion in desktop: sidebar checkbox **Tab completion (Editor)**. In VS Code: `termit.inlineCompletion.enabled`.

## Composer

Shared logic in `@termit/client` (`buildComposerMessage`, `parseComposerPatches`):

1. User attaches context files and writes an instruction.
2. Termit chat returns prose + fenced JSON:

```json
{"patches":[{"path":"app/x.py","hunks":[{"old_text":"a","new_text":"b"}]}]}
```

3. Client parses patches, previews (VS Code diff or dry_run), applies with confirmation.

## Clients

| Path | Role |
|------|------|
| [`termit-client/`](termit-client/) | TypeScript SDK + composer helpers |
| [`vscode-extension/`](vscode-extension/) | Termit inside VS Code / Cursor editor |
| [`termit-desktop/`](termit-desktop/) | Standalone **Termit** app (Electron) |

## Auth

**Termit** `X-API-Key` when `TERMIT_AUTH_ENABLED=true`. No `CURSOR_API_KEY`.
