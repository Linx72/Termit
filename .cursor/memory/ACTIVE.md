# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-16

## Сводка

**0.4.5** — Beta growth: D30 retention + feedback.

- `BetaCohortService` — D7/D30 из feedback + tasks + agent runs
- `GET /api/ops/beta-metrics`, `GET /api/feedback/summary`
- Desktop `BetaFeedbackPanel`, `feedbackOps.ts`
- KPI gate `d30_retention_min` 35% (cohort ≥5)
- Prometheus: `termit_beta_d30_retention_rate`

**Тесты:** 529 OK

## Открытые задачи

- Roadmap 0.3.7–0.4.5 закрыт; следующий track — product growth experiments или platform parity extensions
