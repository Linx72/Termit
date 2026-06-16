# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-16

## Сводка

**0.4.2 выкачен** — Media Studio Fal I2V + Lottie export.

### Fal I2V
- `TERMIT_MEDIA_PUBLIC_BASE_URL` — публичный URL для `/api/media/assets/{id}/file`
- Fallback: `FalVideoProvider.upload_local_image()` → fal CDN
- `_execute_render_job` больше не падает на `provider=fal`

### Lottie
- [`app/services/media_lottie_service.py`](file:///Users/amoros/Projects/Termit/app/services/media_lottie_service.py)
- `POST /api/media/export-lottie`, tool `export_lottie`
- Desktop: кнопка «Экспорт Lottie» в MediaStudioPanel

**Тесты:** 524 OK (skipped=6)

## Открытые задачи

- Следующий пункт roadmap — смотреть `PROJECT_TASK_PROMPT_RU.md` / `MEDIA_STUDIO_ROADMAP_RU.md` (Future optional пуст после 0.4.2)
