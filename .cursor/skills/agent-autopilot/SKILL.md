---
name: Agent Autopilot
description: Autopilot agent runs without human confirm on risky tools; verify after patch enabled
---

# Agent Autopilot

Use with policy preset **`autopilot`** or env `TERMIT_AGENT_AUTO_CONFIRM_RISKY=true`.

## Behavior

- `auto_confirm_risky_tools=true` — `apply_patch`, `execute_command`, `browser_click` get implicit `confirmed=true`
- `verify_after_patch=true` — runs workspace verify after each applied patch
- `max_tool_steps=14`, `execution_mode=hybrid`, online tools enabled

## Workflow

1. Understand task from user prompt + workspace rules
2. Tool loop until done or verify green
3. On verify failure: fix and retry (max ~2 attempts before reporting blocker)
4. Final summary in Russian: files changed, verify output, how to run locally

## When not to use

- Production deploys without review
- Untrusted repos / unknown destructive commands
- User explicitly chose **Guided** in Desktop sidebar

Full prompt: `data/prompts/desktop-autopilot-agent.md`

Preset file: `data/desktop_policy_presets.json` → `preset_id: autopilot`
