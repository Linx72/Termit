---
name: Termit Desktop
description: Use Termit Desktop app tabs, i18n, SectionGuide, Guided vs Autopilot agent modes, and policy presets
---

# Termit Desktop

Use when the user works in **Termit.app** (Electron client) or asks about desktop tabs, Russian UI, or agent run modes.

## Tabs (RU labels)

| Tab | Purpose |
|-----|---------|
| Чат | Streaming chat, @attachments, queue task |
| Компоновщик | Multi-file patches, preview, apply/rollback |
| Редактор | Monaco + inline edit + tab completion |
| План | Plan without code → Build to Composer |
| Терминал | `execute_command` via API |
| Задачи | Background task queue |
| Агенты | Tool loop, confirm, resume |
| Онлайн | Shared runs, heavy eval jobs |
| Задания | Brief → deliverables |
| Справка | Bundled PDF help |

Each tab shows **SectionGuide** (зачем + как пользоваться) from `i18n.ts` keys `sg*`.

## Agent modes (sidebar)

| Mode | Preset | Behavior |
|------|--------|----------|
| **Guided** | solo / team / strict | Risky tools need confirm |
| **Autopilot** | autopilot | `auto_confirm_risky_tools=true`, verify after patch |

API fields: `policy_preset`, `auto_confirm_risky_tools`, `verify_after_patch` on agent run.

## Key paths

- Settings: `clients/termit-desktop/src/settings.ts` (`locale: "ru"` default)
- i18n: `clients/termit-desktop/src/i18n.ts`
- Presets: `data/desktop_policy_presets.json`
- Unified file picker: `clients/termit-desktop/src/WorkspaceFilePickerModal.tsx`
- Unified text modal: `clients/termit-desktop/src/PromptInputModal.tsx`

## UX parity guardrails

- Keep desktop/web UX identical for core flows (attach/open/select/input).
- Avoid `window.prompt` and platform-only picker branches in tab workflows.
- Use `runtimeMode` for backend-control semantics only (server control), not for divergent UI interaction models.

## Verify

```bash
cd clients/termit-desktop && npm run build
cd ../.. && python3 -m unittest tests.test_desktop_runtime_mode_smoke -q
```

## Connect checklist

1. API `http://127.0.0.1:8765` green
2. Ollama models present
3. Workspace folder selected
4. Connect → run agent or chat

Prompt: `data/prompts/desktop-guided-agent.md` or `desktop-autopilot-agent.md`
