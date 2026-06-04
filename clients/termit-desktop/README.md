# Termit desktop UI (web-first)

Standalone **Termit** desktop UI — chat, tasks, and agents over your **Termit API**. Uses local Ollama / finetuned models through Termit routing. **No Cursor account or CURSOR_API_KEY.**

## Runtime architecture

```text
┌──────────────────────────────────────┐
│ Termit UI (React, web-first)         │
│  Chat · Composer · Editor · Tasks · Agents │
└──────────────────┬───────────────────┘
                   │ HTTP / SSE
┌──────────────────▼───────────────────┐
│ Termit server :8765                  │
│  routing · Ollama · apply_patch      │
└──────────────────┬───────────────────┘
                   │
┌──────────────────▼───────────────────┐
│ Ollama :11434 (termit-core-ft, …)    │
└──────────────────────────────────────┘
```

## Prerequisites

- **Node.js 20+** and **npm**
- **Termit server** running, e.g. `uvicorn app.main:app --host 127.0.0.1 --port 8765`
- **Ollama** (if using local models): `./scripts/start_ollama_local.sh`
- **X-API-Key** only when `TERMIT_AUTH_ENABLED=true` (e.g. `dev-key` from `.env`)

## Install and run (web-first, no Electron)

```bash
# Terminal 1 — Termit backend
cd /path/to/Termit
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8765

# Terminal 2 — desktop UI
cd clients/termit-client && npm install && npm run build
cd ../termit-desktop
npm install
npm run dev
```

Production web build:

```bash
npm run build
npm start   # vite preview
```

## Native shell (recommended app bundle, no Electron)

Build and run `TermitShell.app`:

```bash
./scripts/package_termit_shell.sh
open clients/termit-shell/release/TermitShell.app
```

Or run shell directly:

```bash
./scripts/run_termit_shell.sh
```

Details: [`../termit-shell/README.md`](../termit-shell/README.md).

## Electron status

Electron mode is removed from this package. Native desktop distribution now goes through
`TermitShell.app` only.

## One-command dev stack (from repo root)

```bash
./scripts/run_termit_stack.sh
```

See [`../../DESKTOP_QUICKSTART.md`](../../DESKTOP_QUICKSTART.md).

## Usage

1. **Choose repo** — path to Termit clone via built-in modal (for optional auto-start of `uvicorn`)
2. **Connect** — loads providers, routing profiles, finetune adapters into model list
3. **Chat** — streaming (Cmd/Ctrl+Enter), @ file attachments
3. **Composer** — multi-file context → patches → dry-run preview → apply all
4. **Editor** — Monaco workspace files, Cmd+K inline edit with diff preview, Save via `apply_patch`
5. **Tasks** — list and inspect background coding tasks
6. **Agents** — pick a profile, enqueue a run, poll run timeline
7. Optional **workspace folder** (via built-in modal) — required for Editor and improves retrieval / @ file paths

### UX parity baseline

- File/folder flows (`Open file`, `@file`, `@folder`, `Composer @file`) use one built-in selection modal.
- Short text input (`@symbol`, `@web`, path inputs) uses one built-in input modal.
- Key user flows do not use `window.prompt` or platform-specific picker branches.

## Auth

| Server setting | Client |
|----------------|--------|
| `TERMIT_AUTH_ENABLED=false` | Leave X-API-Key empty |
| `TERMIT_AUTH_ENABLED=true` | Use `dev-key` or other key from `.env` |

This is **Termit's** API key (`X-API-Key`), not Cursor's.

## Related clients

- [`../vscode-extension`](../vscode-extension) — Termit inside VS Code/Cursor editor (sidebar + diff patches)
- [`../termit-client`](../termit-client) — TypeScript SDK shared by both

## Why not Cursor SDK?

An earlier prototype used `@cursor/sdk`, which requires a **Cursor billing API key** and Cursor-hosted models. The product is **Termit** — self-hosted orchestration with your Ollama models — so the desktop app talks only to the Termit API.
