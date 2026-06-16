# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-16

## Сводка

- **0.3.6** — SLO/Grafana, DLQ UI, Prometheus metrics, release pack готов.
- **Track 3–5** — desktop UX, release discipline, SLO dashboards закрыты.
- **Track 1** — unstable e2e только nightly (`TERMIT_RUN_UNSTABLE_INTEGRATION=1`).

## Ключевые файлы (0.3.6)

- `app/api/routes/metrics.py` — SLO prometheus gauges
- `deploy/prometheus/`, `deploy/grafana/`, `docker-compose.monitoring.yml`
- `clients/termit-desktop/src/AgentObservabilityPanel.tsx` — DLQ replay
- `clients/termit-client/src/client.ts` — DLQ API
- `docs/OBSERVABILITY_SLO_RU.md`, `VERSION` → 0.3.6

## Открытые задачи

- [ ] Фаза 5: API keys UI, graceful shutdown, signed desktop builds
- [ ] Tag `v0.3.6` + `./scripts/release_all.sh` при готовности к stable
