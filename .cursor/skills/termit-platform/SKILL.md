---
name: termit-platform
description: >-
  Develop the Termit repository — agent loop, ops readiness, verify metrics,
  platform API, eval/smoke, and desktop client wiring. Use when changing backend,
  agents, ops, metrics, or when the user says platform parity, do all, or work on
  Termit core (not end-user app code in other workspaces).
---

# Termit Platform (Cursor)

## When to use

- Any task **inside the Termit repo** for backend, agents, ops, platform layer, eval, clients
- Complements **termit-agent** (identity/workflows) with platform-skill content for API runs

## Artifacts

| Type | Path |
|------|------|
| Platform skill | [data/skills/termit-platform/SKILL.md](../../../data/skills/termit-platform/SKILL.md) |
| System prompt | [data/prompts/termit-platform-agent.md](../../../data/prompts/termit-platform-agent.md) |
| Agent template | `termit-platform-dev` in [data/agent_templates.json](../../../data/agent_templates.json) |

## Quick verify

```bash
.venv/bin/python -m unittest tests.test_platform_parity tests.test_ops_service -q
./scripts/smoke_http.sh
```

## Related Cursor skills

- `termit-agent` — orchestrator identity, phases, do-all style
- `termit-automation` — server automation toggles
- `termit-desktop` — Electron UI
- `termit-prompts` — authoring new prompts/skills
