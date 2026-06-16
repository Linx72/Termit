# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-16

## Сводка

- **0.4.0** — OTEL span export, media trace spans, OnlineAcceleratorPanel.
- **0.3.9** — JSON logs, provider/verify spans, media confirm UI.

## Файлы сессии

- `app/services/trace_span_store.py` — `export_otel_json`
- `app/api/routes/platform.py` — `/spans/otel`
- `app/services/media_generation_service.py` — `_media_trace`
- `clients/termit-desktop/src/App.tsx` — OnlineAcceleratorPanel
- `VERSION` → 0.4.0

## Открытые задачи

- [ ] Hosted beta hardening (TLS prod checklist smoke)
- [ ] Fal I2V / Lottie export (media studio optional)
