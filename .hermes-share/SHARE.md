# .hermes-share — Session Workspace

Initialised: 2026-06-06T20:30:33.918682+00:00

This directory is a shared workspace for Hermes Agent sessions.
All sessions running inside `termit/` can see each other's
context, events, and status via the `session-share` skill.

## Contents

- `registry.db` — SQLite database with sessions, events, shared context
- `SHARE.md` — this file (human-readable reference)

## Commands (inside Hermes with session-share skill loaded)

- `/share status` — who's active and what they're doing
- `/share save <message>` — log an event
- `/share update-context <summary>` — update your shared context
- `/share context` — see full shared context block
- `/share watch` — toggle auto-sync on every turn
