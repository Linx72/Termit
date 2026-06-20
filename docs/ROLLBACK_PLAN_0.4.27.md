# Rollback Plan 0.4.27

## Rollback triggers

- Release desktop bundle не запускается после обновления
- DPO contract / learning loop gate регресс на prod
- Sustained CI regression на `main`

## Fast rollback steps

1. Откат на предыдущий стабильный tag: **`v0.4.24`** (если нужен только ladder без CI-fix) или **`v0.4.25`** (V4 ladder, без desktop assets).
2. Перезапуск API/runtime.
3. Smoke: `/health`, `/healthz`, `./scripts/release_smoke_core.sh`

## Data compatibility

- SQLite / `data/` — без миграций в 0.4.26–0.4.27.
- Smoke-артефакты (`eval_kpi_last.json`, `learning_loop_0423_last.json`) не коммитить после локального smoke.

## Validation after rollback

- `python -m unittest discover -s tests -q`
- `./scripts/smoke_http_core.sh`

## Communication template

- Incident: "Rolled back from v0.4.27 to v0.4.25 due to <reason>."
- Impact window: <start> - <end>
- Next action: hotfix branch, re-run Release workflow, re-ship patch
