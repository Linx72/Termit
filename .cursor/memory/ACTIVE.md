# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-16

## Сводка

- **0.3.7 finetune loop** — `training_loop_full.sh`, baseline auto-promote, weekly cron, provider/cost Prometheus metrics.

## Файлы сессии

- `scripts/eval_baseline_promote.py`, `scripts/training_loop_weekly.sh`
- `scripts/install_stage1_scheduler.sh` — mode `training-loop`
- `app/api/routes/metrics.py` — fallback/cost/model_usage gauges
- `deploy/grafana/dashboards/termit-slo.json`, `deploy/prometheus/alerts.yml`

## Открытые задачи

- [ ] +5% eval pass после stage1 cycle (запустить `TERMIT_EVAL_MIN_IMPROVEMENT_FOR_PROMOTE=0.05` после real train)
- [ ] Tag 0.3.7 после первого green weekly loop на prod
