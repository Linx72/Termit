# Termit (desktop app)

Standalone **Termit** desktop client — chat, tasks, and agents over your **Termit API**. Uses local Ollama / finetuned models through Termit routing. **No Cursor account or CURSOR_API_KEY.**

## Architecture

```text
┌──────────────────────────────────────┐
│ Termit app (Electron + React)        │
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

## Install and run

```bash
# Terminal 1 — Termit backend
cd /path/to/Termit
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8765

# Terminal 2 — desktop app
cd clients/termit-client && npm install && npm run build
cd ../termit-desktop
npm install
npm run dev
```

Packaged build:

```bash
npm run build
npm start
npm run package   # output in release/
```

The packaged app name is **Termit** (`productName` in electron-builder).

## One-command dev stack (from repo root)

```bash
./scripts/run_termit_stack.sh
```

See [`../../DESKTOP_QUICKSTART.md`](../../DESKTOP_QUICKSTART.md).

## Usage

1. **Choose repo** — path to Termit clone (for optional auto-start of `uvicorn`)
2. **Connect** — loads providers, routing profiles, finetune adapters into model list
3. **Chat** — streaming (Cmd/Ctrl+Enter), @ file attachments
3. **Composer** — multi-file context → patches → dry-run preview → apply all
4. **Editor** — Monaco workspace files, Cmd+K inline edit with diff preview, Save via `apply_patch`
5. **Tasks** — list and inspect background coding tasks
6. **Agents** — pick a profile, enqueue a run, poll run timeline
7. Optional **workspace folder** — required for Editor and improves retrieval / @ file paths

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
