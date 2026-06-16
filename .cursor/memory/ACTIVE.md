# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-16

## Сводка

**0.4.3 выкачен** — Media observability + hosted media smoke.

### Trace spans
- `media.render_video`, `media.export_gif`, `media.export_lottie` в TraceSpanStore

### Eval + smoke
- **MS11** — Lottie export scenario
- `hosted_smoke.sh` step 5/5 — optional `TERMIT_HOSTED_MEDIA_EXPECT=true`
- `deploy/docker.env.example` — Media Studio block

**Тесты:** 526+ OK после релиза

## Открытые задачи

- Мастер-план `PROJECT_TASK_PROMPT_RU.md` закрыт через 0.4.3; следующий «do all» — новый этап 0.4.4+ (см. KPI targets / product growth)
