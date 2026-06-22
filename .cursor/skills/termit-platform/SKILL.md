---
name: Termit Platform
description: Develop the Termit codebase — agent loop, ops readiness, verify metrics, platform API, eval/smoke, and Cursor-like clients
---

# Termit Platform

Use when changing **this repository** (backend, agents, ops, desktop client wiring, eval), not end-user app code in other workspaces.

## Scope

| Area | Key paths |
|------|-----------|
| Wiring | `app/state.py`, `app/core/config.py`, `app/domain/schemas.py`, `app/main.py` |
| Agent loop | `app/services/agent_loop_service.py`, `agent_service.py`, `multi_agent_orchestrator.py` |
| Ops / health | `app/services/ops_service.py`, `alert_health_service.py`, `app/api/routes/ops.py` |
| Metrics | `app/services/tool_loop_metrics.py`, `app/api/routes/metrics.py` |
| Platform | `app/api/routes/platform.py`, `skill_store.py`, `mcp_registry_service.py` |
| Clients | `clients/termit-client/`, `clients/termit-desktop/` |
| Tests | `tests/test_platform_parity.py`, `tests/test_platform_e2e.py`, `tests/test_ops_service.py` |

## Workflow

1. **Read session memory** — `.cursor/memory/ACTIVE.md` before non-trivial work
2. **Minimal diff** — match existing patterns; do not refactor unrelated code
3. **Implement** — wire config in `Settings` → `state.py` → service → route → schema
4. **Test** — relevant `python3 -m unittest tests.test_* -q`; widen to `discover -s tests` if scope is broad
5. **Runtime smoke** (backend/API touched) — `./scripts/smoke_http.sh` or `./scripts/smoke_all.sh`
6. **Report** — passed/failed counts, HTTP codes; answers in **Russian**

## Ops & verify quality

When touching agent reliability or observability:

- **Readiness** — `GET /api/ops/readiness` includes `agent_verify_quality` when verify observations exist
- **Metrics** — `GET /api/ops/agent-runs/metrics` exposes `tool_loop_verify_pass_rate`, retries, passes/failures
- **Thresholds** — `TERMIT_AGENT_ALERT_MIN_VERIFY_PASS_RATE` (default `0.70`); health gate in `alert_health_service.py`
- **Alerts** — `POST /api/ops/alerts/dispatch` webhook payload includes verify rate + threshold
- **Per-run override** — `verify_max_retries` on `AgentRunRequest` (0–5)

## Tool loop conventions

- Desktop sends `use_tool_loop: true`; respect profile `enabled_tools`
- Verify after patch: bounded in-loop retries via `agent_verify_max_retries` / per-run override
- Checkpoints must persist `verify_retries_used` for resume/confirm flows

## Do not

- Ask user to restart server or run tests — run them yourself
- Commit unless explicitly requested
- Save delivery PDF/MD reports

Full system prompt: `data/prompts/termit-platform-agent.md`

Cursor skill: `.cursor/skills/termit-platform/SKILL.md`
