# Migration Notes 0.4.5

## Scope

Beta D30 retention metrics + Desktop feedback panel

Previous stable: `v0.4.4`.

## Configuration changes

- Review `.env.example` for new or renamed keys since `v0.4.4`.
- No schema migrations expected unless noted in commit history.

## CI / release process

- Fast gate (PR/main): `.github/workflows/ci.yml`
- Deep gate (nightly): full eval suite in CI
- Release gate (local/manual): `TERMIT_EVAL_GATE_TIER=release ./scripts/release_smoke_extended.sh`
- Deterministic core: `./scripts/release_smoke_core.sh`

## Operator checks after upgrade

1. `./scripts/release_smoke_core.sh`
2. `GET /health`, `GET /healthz`, `GET /api/ops/readiness` => 200
3. Desktop (if used): `cd clients/termit-desktop && npm run build`

