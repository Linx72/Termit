# Migration Notes 0.3.5

## Scope

This stability release finalizes deterministic release smoke split and hardens release handoff:
- deterministic/core and extended smoke profiles are available as separate entrypoints,
- nightly workflow runs only extended profile,
- release helper script now pushes the current branch (instead of hardcoded `main`).

## Configuration changes

No required new environment variables in this release.

## CI / release process changes

- Core release smoke:
  - `./scripts/release_smoke_core.sh`
- Extended release smoke:
  - `./scripts/release_smoke_extended.sh`
- Nightly extended run:
  - `.github/workflows/nightly-extended-smoke.yml`

## API / runtime compatibility

- No breaking API changes introduced by this release block.
- Existing smoke/eval endpoints remain unchanged.

## Operator checks after upgrade

1. Verify deterministic release profile:
   - `./scripts/release_smoke_core.sh`
2. Verify full profile in nightly context:
   - `./scripts/release_smoke_extended.sh`
3. Verify health endpoints:
   - `GET /health` => 200
   - `GET /healthz` => 200
   - `GET /api/metrics/thresholds` => 200
   - `GET /api/ops/readiness` => 200

