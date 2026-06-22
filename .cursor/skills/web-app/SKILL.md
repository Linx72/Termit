---
name: Web App
description: Scaffold and iterate Vite/React (or Node) web applications with dev server and verify loop
---

# Web App

Use for **SPA / frontend** work: Vite, React, TypeScript, Tailwind, component libraries.

## Stack detection

1. `read_file` `package.json` — scripts: `dev`, `build`, `test`, `lint`
2. Prefer existing conventions (paths, router, state library)

## Workflow

1. **Scaffold** (greenfield): `npm create vite@latest` or extend existing `src/`
2. **Dev** — `npm run dev` in background; note URL (often `:5173`)
3. **Implement** — small patches per component/route; use retrieval for large repos
4. **Verify** — `npm test` → `npm run lint` → `npm run build` (chain from package.json)
5. **Preview** — `browser_navigate` + `browser_snapshot` on dev URL when `allow_online=true`

## File layout (Vite default)

- `src/App.tsx`, `src/main.tsx`, `index.html`
- Tests: `*.test.tsx` next to components or `src/__tests__/`

## Rules

- Do not commit `node_modules` or `.env` secrets
- Prefer accessible markup (labels, aria) for forms
- Mobile-first CSS when user asks for responsive UI
- After `apply_patch`, assume verify runs automatically — keep builds green

## Composer output

For multi-file UI changes, return JSON patches with `path` under `src/`.
