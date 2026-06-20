# Release flow: rc → stable → hotfix

Termit uses semantic-ish versioning in `VERSION` and git tags `v{VERSION}`.

## Branches and tags

| Stage | Branch / tag | Purpose |
|-------|----------------|---------|
| Development | `main` | Integration; CI fast + deep gates |
| Release candidate | `release/vX.Y.Z-rc.N` or tag `vX.Y.Z-rc.N` | Stabilization before stable |
| Stable | tag `vX.Y.Z` on `main` (or release branch) | Production / desktop builds |
| Hotfix | `hotfix/vX.Y.Z-pN` from stable tag | Minimal patch without feature drift |

## Standard stable release

1. **Prepare pack** (changelog + migration + rollback):
   ```bash
   ./scripts/release_pack.sh X.Y.Z --prev PREV --notes "One-line summary"
   ```
2. Edit `CHANGELOG.md` with full Added/Changed/Fixed sections.
3. Set `VERSION` to `X.Y.Z`.
4. **Quality**:
   ```bash
   ./scripts/pre_release_check.sh
   # или по частям:
   ./scripts/release_gate_local.sh
   TERMIT_RELEASE_RUN_STAGING=true ./scripts/pre_release_check.sh
   ```
   После live eval в `release_smoke` fixture `data/eval_fixtures/patch_sample.txt` сбрасывается на baseline (`reset_eval_patch_fixture.sh`). Если гоняли eval вручную — `./scripts/reset_eval_patch_fixture.sh`.
5. **Ship**:
   ```bash
   git add VERSION CHANGELOG.md docs/MIGRATION_NOTES_X.Y.Z.md docs/ROLLBACK_PLAN_X.Y.Z.md
   git commit -m "Release X.Y.Z"
   git tag vX.Y.Z
   ./scripts/release_all.sh
   ```

## Release candidate (rc)

1. Branch from `main`: `git checkout -b release/vX.Y.Z-rc.1`
2. Run extended smoke + nightly-equivalent checks locally.
3. Tag `vX.Y.Z-rc.1`; fix issues on the branch; increment rc until green.
4. Merge rc branch to `main`; tag stable `vX.Y.Z`.

## Hotfix

1. `git checkout -b hotfix/vX.Y.Z-p1 vX.Y.Z`
2. Minimal fix + targeted tests.
3. `./scripts/release_pack.sh X.Y.Z-p1 --prev X.Y.Z --notes "Hotfix: ..."`
4. Bump `VERSION`, tag `vX.Y.Z-p1`, run `release_smoke_core.sh`, `./scripts/release_all.sh`.
5. Cherry-pick or merge hotfix back to `main`.

## Rollback

Follow `docs/ROLLBACK_PLAN_{version}.md` for the deployed version. Always verify:

- `GET /health`, `GET /healthz`, `GET /api/ops/readiness`
- `./scripts/release_smoke_core.sh`

## Related

- [`RELEASE_CHECKLIST.md`](../RELEASE_CHECKLIST.md)
- [`scripts/release_all.sh`](../scripts/release_all.sh)
- [`scripts/pre_release_check.sh`](../scripts/pre_release_check.sh)
- [`scripts/release_gate_staging.sh`](../scripts/release_gate_staging.sh)
- [`scripts/release_pack.sh`](../scripts/release_pack.sh)
