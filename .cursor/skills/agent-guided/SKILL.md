---
name: Agent Guided
description: Guided agent runs with human confirm on apply_patch, execute_command, and browser_click
---

# Agent Guided

Use with policy presets **solo**, **team**, or **strict** — not autopilot.

## Behavior

- `auto_confirm_risky_tools=false`
- Tool loop pauses on `requires_confirmation` → state `awaiting_confirmation`
- User approves in Desktop **Agents** or via `POST .../confirm`

## Recommended tools

`list_files`, `read_file`, `apply_patch`, `execute_command` (+ online tools if preset allows)

## Agent loop

1. Read → propose change
2. Call risky tool without `confirmed` → preview / confirmation request
3. After approval, resume with same checkpoint
4. Verify after patch when enabled

## Presets

| Preset | Steps | Online | Tools |
|--------|-------|--------|-------|
| solo | 8 | no | core patch/cmd |
| team | 10 | yes | + web |
| strict | 5 | no | read + patch only |

Full prompt: `data/prompts/desktop-guided-agent.md`
