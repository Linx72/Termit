# Migration Notes 0.4.14

## Scope

MCP prompt picker in Desktop and opt-out for MCP context injection.

Previous stable: `v0.4.13`.

## Configuration changes

- `AgentRunRequest.mcp_context_inject`: omit or `true` (default) to inject; `false` to skip resource/prompt auto-inject.
- Desktop: Settings → Platform MCP → **Auto-inject MCP context on run** (stored in local settings).

## Operator checks after upgrade

1. `./scripts/release_smoke_core.sh`
2. Desktop: MCP prompt picker → preview → Insert into Agent (plan)
3. Disable auto-inject checkbox → run should not emit `mcp_context_injected` / `mcp_prompt_injected`
