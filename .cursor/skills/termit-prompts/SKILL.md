---
name: termit-prompts
description: >-
  Termit agent system prompts and platform skills in data/prompts/ and
  data/skills/. Use when creating or editing prompts, skills, agent templates,
  or wiring skill_ids in data/agent_templates.json.
---

# Termit Prompts & Skills

## Layout

| Type | Location | Loaded by |
|------|----------|-----------|
| System prompts | `data/prompts/*.md` | Referenced in `agent_templates.json` system_prompt |
| Platform skills | `data/skills/<id>/SKILL.md` | `SkillStore`, API `/api/platform/skills` |
| Cursor skills | `.cursor/skills/<name>/SKILL.md` | Cursor agent |
| Agent templates | `data/agent_templates.json` | `POST /api/projects/agent-templates`, Desktop seed |

## Prompt catalog

| File | Agent template |
|------|----------------|
| `web-app-builder.md` | `web-app-vite` |
| `research-fast.md` | `research-fast` |
| `online-project-manager.md` | `online-project-manager` |
| `desktop-guided-agent.md` | `termit-desktop-guided` |
| `desktop-autopilot-agent.md` | `termit-desktop-autopilot` |
| `desktop-ux-authoring.md` | (Cursor / human — UI work) |
| `termit-platform-agent.md` | `termit-platform-dev`, `desktop-cursor-parity-stable` |

## Platform skill catalog

| skill_id | Purpose |
|----------|---------|
| `termit-platform` | Termit repo backend, ops, agent loop, smoke |
| `web-app` | Vite/React verify loop |
| `online-research` | Fast/deep web research |
| `online-project` | Assignment deliverables |
| `termit-desktop` | Desktop tabs & modes |
| `agent-guided` | Confirm risky tools |
| `agent-autopilot` | Auto confirm + verify |
| `cross-platform-atomic` | Multi-platform atomic steps |
| `fix-ci`, `write-tests`, `security-review` | Task templates |

## Create a new skill

1. `mkdir data/skills/my-skill`
2. Add `SKILL.md` with YAML frontmatter `name`, `description`
3. Optional: `data/prompts/my-skill-agent.md` for long system text
4. Add template in `data/agent_templates.json` with `"skill_ids": ["my-skill"]`
5. Test: `python3 -m unittest tests.test_platform_parity -q`

## Create agent template entry

```json
{
  "template_id": "my-agent",
  "name": "My Agent",
  "system_prompt": "Follow skill my-skill and data/prompts/my-skill-agent.md.",
  "skill_ids": ["my-skill"],
  "use_tool_loop": true,
  "enabled_tools": ["read_file", "apply_patch"]
}
```

Seed: `./scripts/seed_web_agents.sh` or Desktop **Задания** buttons.

## Cursor skills (this repo)

- `termit-agent` — general Termit orchestrator
- `termit-platform` — develop Termit codebase (backend/ops/agents)
- `termit-automation` — do_all_automatic
- `termit-desktop` — Electron UI
- `web-app`, `online-project` — vertical workflows

Reference: [DESKTOP_UX_TASK_PROMPT_RU.md](../../DESKTOP_UX_TASK_PROMPT_RU.md), [AUTOMATION_TASK_PROMPT_RU.md](../../AUTOMATION_TASK_PROMPT_RU.md)
