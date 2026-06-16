---
name: Online Project
description: Execute internet-wide assignments with research, build, and deliverables
---

# Online Project

Use when the user gives an **assignment** that spans the web and local workspace (research → implement → deliver → report).

## Prerequisites

- Agent profile: `allow_online=true`
- Tools: `web_search`, `web_automation`, `browser_navigate`, `browser_snapshot`, `read_file`, `list_files`, `apply_patch`, `execute_command`
- Optional: `browser_click` only with `confirmed=true`

## Workflow

1. **Brief** — If no assignment folder exists, tell the user to `POST /api/assignments` or create under `data/assignments/<id>/` with `brief.md`.
2. **Plan** — 3–7 steps: research → evidence → build → verify → report. State success criteria from `brief.md`.
3. **Research** — `web_search` with citations; open top URLs via `web_automation` or `browser_navigate` + `browser_snapshot` for JS sites. Optional MCP: enable `termit-browser` preset and use `mcp_invoke` (see `docs/MCP_BROWSER_RU.md`).
4. **Build** — Artifacts in `deliverables/` (markdown, code, exports). Use `apply_patch` / `execute_command` in repo when needed.
5. **Journal** — Append progress to `journal/log.md` (what was tried, URLs, blockers).
6. **Verify** — Check success criteria; run project tests if code changed.
7. **Report** — Summary with links, files created, and explicit **blockers** (login, captcha, paywall).

## Safety

- Stop on login/CAPTCHA; do not guess credentials.
- No `browser_click` or destructive shell without confirmation.
- Cite every external fact with URL.

## Blockers

Report clearly: `login_required`, `captcha`, `access_denied`, `search_unavailable` (start SearXNG or set search API key).
