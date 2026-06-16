# Observability & SLO (Termit)

Termit экспортирует метрики в формате Prometheus на `GET /api/metrics/prometheus`. Пороги алертов — `GET /api/metrics/thresholds`.

## Быстрый старт (Docker)

```bash
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d
```

| Сервис | URL |
|--------|-----|
| Termit API | http://localhost:8080 (через Caddy) или :8765 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (admin / `TERMIT_GRAFANA_PASSWORD` или `admin`) |

Dashboard: **Termit → Termit SLO**.

## Ключевые SLO-метрики

| Метрика | Назначение |
|---------|------------|
| `termit_agent_dead_letter_rate` | Доля failed среди terminal runs (порог 15%) |
| `termit_agent_lifecycle_completion_rate` | Успешные завершения |
| `termit_agent_stale_*_runs` | Застрявшие queued/running |
| `termit_tool_loop_tool_errors` | Ошибки tool loop |
| `termit_agent_runs_total{state="failed"}` | Failed runs по state |

## Алерты (Prometheus)

Файл: [`deploy/prometheus/alerts.yml`](file:///Users/amoros/Projects/Termit/deploy/prometheus/alerts.yml)

- **TermitHighDeadLetterRate** — dead-letter > 15% (5m)
- **TermitFailedRunsSpike** — >5 failed за 15m
- **TermitQueueStuck** — stale runs > 0 (10m)
- **TermitHighToolLoopErrors** — elevated tool errors
- **TermitWorkersDown** — alive < configured

## Webhook-алерты (без Grafana)

```bash
export TERMIT_ALERT_WEBHOOK_URL=https://hooks.slack.com/...
curl -X POST http://127.0.0.1:8765/api/ops/alerts/dispatch -H "X-API-Key: dev-key"
```

## Desktop / ops UI

- **RuntimeStatusBar** — active runs, queue, outcome classes
- **AgentObservabilityPanel** — dead-letter rate, DLQ replay
- **HealthDashboard** — lifecycle, eval KPI

## Связанные файлы

- [`docker-compose.monitoring.yml`](file:///Users/amoros/Projects/Termit/docker-compose.monitoring.yml)
- [`deploy/prometheus/prometheus.yml`](file:///Users/amoros/Projects/Termit/deploy/prometheus/prometheus.yml)
- [`KPI_DASHBOARD_SPEC.md`](file:///Users/amoros/Projects/Termit/KPI_DASHBOARD_SPEC.md)
