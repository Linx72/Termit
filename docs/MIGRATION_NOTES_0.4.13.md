# Migration Notes 0.4.13

## Scope

MCP prompt inject in plan mode and Desktop resource picker for Termit 0.4.13.

Previous stable: `v0.4.12`.

## Configuration changes

- No new required env keys.
- Plan-mode runs with MCP tools receive `[MCP plan prompts]` block in context.
- Desktop Platform panel: resource picker for enabled MCP servers with resources.

## Operator checks after upgrade

1. `./scripts/release_smoke_core.sh`
2. `GET /health`, `GET /healthz` => 200
3. Desktop: Platform → MCP → select server with resources → preview → Insert into Composer
