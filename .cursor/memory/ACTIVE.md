# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-16

## Сводка

- **0.3.8** — Desktop North Star UX + eval observability.
- **0.3.7** — finetune loop closure, KPI gate +5%, tag `v0.3.7`.

## Файлы сессии

- `clients/termit-desktop/src/App.tsx` — WorkflowHubPanel + KpiGatePanel
- `app/services/eval_service.py` — `pass_rate_by_category`
- `app/api/routes/metrics.py` — Prometheus eval metrics
- `deploy/prometheus/alerts.yml` — WorkersDown + ProviderFailureBurst fix
- `VERSION` → 0.3.8

## Открытые задачи

- [ ] Tag/push `v0.3.8` после commit
- [ ] Следующий этап: media studio human-approve gate, structured JSON logs (OBSERVABILITY_CHECKLIST)
