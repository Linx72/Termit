# Migration Notes 0.4.12

## Scope

MCP resource context injection and read/prompt agent tools for Termit 0.4.12.

Previous stable: `v0.4.11`.

## Configuration changes

- No new required env keys.
- Agents with `mcp_invoke` now also receive `mcp_read_resource` / `mcp_get_prompt` in the tool loop.
- Allowed MCP servers with resources get a short catalog injected at run start (`mcp_context_injected` event).

## CI / release process

- Fast gate (PR/main): `.github/workflows/ci.yml`
- Release gate: `TERMIT_EVAL_GATE_TIER=release ./scripts/release_smoke_extended.sh`
- Deterministic core: `./scripts/release_smoke_core.sh`

## Operator checks after upgrade

1. `./scripts/release_smoke_core.sh`
2. `GET /health`, `GET /healthz`, `GET /api/ops/readiness` => 200
3. Optional: run eval scenario `P4` (`platform_mcp_read`)
