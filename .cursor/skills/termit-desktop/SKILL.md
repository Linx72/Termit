---
name: termit-desktop
description: >-
  Termit Desktop Electron app: i18n RU/EN, SectionGuide per tab, Guided/Autopilot
  modes, policy presets, npm build and package_desktop. Use when editing
  termit-desktop UI, section guides, Russian translations, or App.tsx tabs.
---

# Termit Desktop (Cursor)

## When to apply

- Правки `clients/termit-desktop/` — UI, i18n, SectionGuide, sidebar
- «переведи интерфейс», «опиши раздел», «Guided / Autopilot toggle»
- Сборка `.app`: `./scripts/package_desktop.sh`

**Platform skill (agents):** [`data/skills/termit-desktop/SKILL.md`](../../data/skills/termit-desktop/SKILL.md)

**Authoring prompt:** [`data/prompts/desktop-ux-authoring.md`](../../data/prompts/desktop-ux-authoring.md)

## Architecture

```
clients/termit-desktop/src/
  i18n.ts           # ru + en messages, tabLabel(), t()
  SectionGuide.tsx  # sg* keys per tab
  App.tsx           # tabs, sidebar, agent runs
  settings.ts       # locale default "ru", agentRunMode
```

Policy presets → API: `data/desktop_policy_presets.json`

## Add / change section guide

1. Keys in `i18n.ts`: `sgChatTitle`, `sgChatPurpose`, `sgChatSteps` (steps newline-separated)
2. Register in `SectionGuide.tsx` → `SECTION_META`
3. `<SectionGuide locale={locale} section="chat" />` in tab body

## Agent modes in UI

- `settings.agentRunMode`: `"guided"` | `"autopilot"`
- Autopilot forces `policy_preset: "autopilot"` on `createAgentRun`

## Verify

```bash
cd clients/termit-desktop && npm run build
./scripts/package_desktop.sh
```

## Related prompts

| Prompt | Use |
|--------|-----|
| [desktop-guided-agent.md](../../data/prompts/desktop-guided-agent.md) | Guided agent system text |
| [desktop-autopilot-agent.md](../../data/prompts/desktop-autopilot-agent.md) | Autopilot agent system text |
| [desktop-ux-authoring.md](../../data/prompts/desktop-ux-authoring.md) | UI/i18n edits |

Master doc: [DESKTOP_UX_TASK_PROMPT_RU.md](../../DESKTOP_UX_TASK_PROMPT_RU.md)
