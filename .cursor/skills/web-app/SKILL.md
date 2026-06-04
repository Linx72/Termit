---
name: web-app
description: >-
  Build Vite/React web apps in Termit: web-app skill, web-app-vite agent template,
  npm dev/test/build verify, workspace-scripts API, Terminal quick commands.
---

# Termit Web App Builder

## When to use

- User builds SPA, React, Vite, frontend, landing, dashboard
- Template `web-app-vite`, skill `web-app`

## Docs

- [WEB_APPS_RU.md](../../../WEB_APPS_RU.md)
- Prompt: [data/prompts/web-app-builder.md](../../../data/prompts/web-app-builder.md)
- Skill: [data/skills/web-app/SKILL.md](../../../data/skills/web-app/SKILL.md)

## API

```bash
curl -s http://127.0.0.1:8765/api/tools/workspace-scripts
```

Returns `dev_command`, `verify_command` from `package.json`.

## Agent

Create from template **web-app-vite**; enable **allow_online** for browser preview of `npm run dev`.

## Desktop

Terminal tab loads **npm run dev**, verify, lint, build as quick buttons when `package.json` exists.
