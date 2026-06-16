# Rollback Plan 0.4.0

## Rollback triggers

- Core smoke (`./scripts/release_smoke_core.sh`) fails on previously green paths
- Sustained CI regression on `main` after deploy
- Critical runtime incident (auth, data loss, queue stuck)

## Fast rollback steps

1. Roll back to previous stable tag (`v0.3.9`).
2. Restart Termit API/runtime (`docker compose up -d --build` or systemd/LaunchAgent).
3. Smoke:
   - `/health`, `/healthz`, `/api/metrics/thresholds`, `/api/ops/readiness`
4. `./scripts/release_smoke_core.sh`

## Data compatibility

- Check commit history for SQLite schema or data migrations since `v0.3.9`.
- Backup `data/` and SQLite path before rollback if migrations were applied.

## Validation after rollback

- `./.venv/bin/python -m unittest discover -s tests -q`
- `./scripts/smoke_http_core.sh`

## Communication template

- Incident: "Rolled back from v0.4.0 to v0.3.9 due to <reason>."
- Impact window: <start> - <end>
- Next action: fix on branch, re-run release pack, re-ship patch/hotfix

