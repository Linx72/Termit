# Rollback Plan 0.3.3

## Rollback triggers

Initiate rollback if one or more occur:
- persistent increase in failed/dead-lettered runs after deployment,
- severe queue starvation despite healthy workers,
- desktop agent path fails to create/use stable template,
- parity eval gate drops below threshold unexpectedly.

## Fast rollback steps

1. Roll back to previous release tag (`v0.3.2`) in deployment target.
2. Restart Termit API process.
3. Re-run smoke checks:
   - `/health`
   - `/healthz`
   - `/api/ops/readiness`
   - `/api/ops/agent-runs/metrics`
4. Verify queue recovers (`queued` drain, `running` transitions to terminal states).

## Config rollback guidance

- Remove or ignore `TERMIT_AGENT_QUEUE_STUCK_TIMEOUT_SECONDS` (safe if left unset).
- If needed, restore previous env snapshot for release.

## Data compatibility

- No destructive schema/data migrations in this release.
- New eval scenarios are additive.
- New metrics fields are additive.

## Validation after rollback

- `./.venv/bin/python -m unittest tests.test_agent_service tests.test_agent_loop_service -q`
- `./scripts/smoke_http.sh`
- optional: full `python -m unittest discover -s tests -q`

## Communication template

- Incident summary: "Rolled back from 0.3.3 to 0.3.2 due to <reason>."
- Impact window: `<start> - <end>`
- Current state: healthy/degraded + key metrics
- Next action: isolate root cause in 0.3.3 branch and re-ship patch
