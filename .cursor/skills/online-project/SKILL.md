---
name: online-project
description: >-
  Run Termit online assignments end-to-end: web_search, browser tools, assignment
  workspaces under data/assignments/, deliverables and journal. Use when the user
  wants internet research, online projects, web automation, or online-project-manager agent.
---

# Termit Online Project

## When to use

- User asks for online project, web research, assignment, deliverables
- Working with `POST /api/assignments`, `task_type: online_project` or `online_research`
- Agent templates: `online-project-manager`, `research-fast`, `research-deep`

## Setup (once per machine)

```bash
cd ~/Projects/Termit
./scripts/setup_online_stack.sh
TERMIT_INSTALL_PLAYWRIGHT=1 ./scripts/setup_online_stack.sh  # optional JS sites
./scripts/restart_server.sh
```

Guide: [ONLINE_PROJECTS_RU.md](../../../ONLINE_PROJECTS_RU.md)

## Create assignment

```bash
curl -s -X POST http://127.0.0.1:8765/api/assignments \
  -H 'Content-Type: application/json' \
  -d '{"title":"...","brief":"...","success_criteria":["..."]}'
```

## Agent profile

From template `online-project-manager`:

- `allow_online=true` (required)
- `skill_ids`: `["online-project"]`
- Full system prompt: [data/prompts/online-project-manager.md](../../../data/prompts/online-project-manager.md)

Bundled skills: `data/skills/online-project/`, `data/skills/online-research/`

## Verify

```bash
curl -s http://127.0.0.1:8765/health
curl -s "http://127.0.0.1:8888/search?q=test&format=json" | head -c 200
```
