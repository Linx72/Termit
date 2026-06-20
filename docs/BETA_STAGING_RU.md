# Beta staging — telemetry, cohort D30, product gates

Этап **0.4.24**: product KPI из real beta telemetry на hosted/staging.

## Beta heartbeat (real users)

Desktop/клиент шлёт session heartbeat без rating (авто при connect, ≤1/сутки):

- Desktop: `recordBetaActivityIfDue` → `POST /api/ops/beta/activity`
- Actor id: `localStorage` `termit-device-id`

```bash
curl -X POST http://127.0.0.1:8765/api/ops/beta/activity \
  -H "Content-Type: application/json" \
  -d '{"session_id":"user-abc123","source":"desktop"}'
```

## Deploy (Colima)

```bash
./scripts/start_colima_and_deploy_beta.sh
# или вручную: colima start && ./scripts/deploy_hosted_beta.sh
```

Данные попадают в feedback JSONL → `BetaCohortService` считает D30 retention.

## Staging release gate

```bash
./scripts/release_gate_staging.sh
# или полный local + staging:
TERMIT_RELEASE_RUN_STAGING=true ./scripts/release_gate_local.sh
```

Шаги: hosted smoke → seed product KPI в container → bootstrap 5 beta actors → beta gate (`gate_mode=real`).

## Real beta bootstrap

```bash
python scripts/bootstrap_beta_staging_cohort.py --base-url http://127.0.0.1:8080 --actors 5
```

`gate_mode=real`: `tracked_actors ≥ 5` и `active_users_7d ≥ 3` (без ожидания D30 30 дней).

Отчёт: `data/beta_staging_gate_last.json`

## Telemetry report (CLI)

```bash
python scripts/beta_telemetry_report.py --base-url http://127.0.0.1:8765 --strict
```

## Dev seed (local only)

```bash
TERMIT_BETA_DEV_SEED=true ./scripts/seed_beta_cohort_dev.py --force
```

Пишет `data/beta_cohort_meta.json` с `dev_only: true` — plan status показывает `beta_cohort_dev_seed`, не `beta_cohort`.

## DoD 0.4.24

| Критерий | Как проверить |
|----------|----------------|
| cohort_size_d30 ≥ 5 | `GET /api/ops/beta-metrics` на staging |
| product gates green | `GET /api/desktop/kpi-gates` → `overall_passed=true` |
| deploy | `./scripts/deploy_hosted_beta.sh` (Docker/Colima) |

## Связанные скрипты

- [`deploy_hosted_beta.sh`](file:///Users/amoros/Projects/Termit/scripts/deploy_hosted_beta.sh)
- [`hosted_smoke.sh`](file:///Users/amoros/Projects/Termit/scripts/hosted_smoke.sh) — включает `POST /api/ops/beta/activity`
- [`plan_status_dev_green.sh`](file:///Users/amoros/Projects/Termit/scripts/plan_status_dev_green.sh) — local dev shortcut
