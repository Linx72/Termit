# Rollback Plan 0.3.5

## Rollback triggers

Initiate rollback if one or more occur:
- deterministic/core smoke starts failing on previously green scenarios,
- nightly extended profile causes persistent regressions in CI,
- release helper push/tag flow fails due to branch/tag mismatch.

## Fast rollback steps

1. Roll back deployment target to previous stable tag (`v0.3.4`).
2. Restart Termit API/runtime services.
3. Re-run smoke checks:
   - `/health`
   - `/healthz`
   - `/api/metrics/thresholds`
   - `/api/ops/readiness`
4. Re-run deterministic release profile:
   - `./scripts/release_smoke_core.sh`

## Data compatibility

- No schema migrations in this release.
- No destructive data changes expected.

## Validation after rollback

- `./.venv/bin/python -m unittest tests.test_platform_e2e tests.test_agents_api -q`
- `./scripts/smoke_http_core.sh`
- optional: `./.venv/bin/python -m unittest discover -s tests -q`

## Communication template

- Incident summary: "Rolled back from 0.3.5 to 0.3.4 due to <reason>."
- Impact window: `<start> - <end>`
- Current state: healthy/degraded + key metrics
- Next action: isolate root cause in 0.3.5 branch and re-ship patch

