# ADR-001: Media Studio в Termit

| Поле | Значение |
|------|----------|
| Статус | **Принято** (Фаза 0 Discovery) |
| Дата | 2026-06-03 |
| Владелец | Termit platform |
| Связано | [`MEDIA_STUDIO_ROADMAP_RU.md`](MEDIA_STUDIO_ROADMAP_RU.md), [`MEDIA_STUDIO_PHASE0_RU.md`](MEDIA_STUDIO_PHASE0_RU.md) |

---

## Контекст

Termit — local-first AI-оркестратор с agent loop, MCP, skills и deliverables (`data/assignments/`). Генерации изображений, анимации и видео **нет**. Пользователю нужен **studio-уровень**: бриф → storyboard → сцены → озвучка → монтаж → экспорт под площадки, с бюджетом и QA.

Альтернативы:

1. **Только MCP** (ComfyUI, ffmpeg MCP) — быстрый POC, нет единого asset store и cost control.
2. **Отдельное SaaS** — дублирует harness, нет связи с agent runs и eval.
3. **Нативный Media Layer в Termit** — выбрано.

---

## Решение

Ввести подсистему **Termit Media Studio**: async jobs, asset store, provider adapters, native tools в agent loop, multi-agent presets, Desktop preview.

### Стратегия провайдеров (зафиксировано в Фазе 0)

| Режим | Описание | Когда |
|-------|----------|-------|
| **Hybrid studio (default)** | Cloud: images + I2V + TTS + vision QA; Local: ffmpeg compose, subtitles burn-in, exports | Продакшен, «studio» |
| **Cloud-only** | Всё через Fal/Replicate/OpenAI; ffmpeg в облаке (Lambda Remotion) опционально | Нет GPU на хосте |
| **Local-first** | ComfyUI + AnimateDiff + ffmpeg; cloud только fallback | Приватность, offline |

**Default для Termit:** `hybrid studio` — минимизирует cost на монтаже, максимизирует качество на генерации.

### Primary cloud bundle (v1)

| Слой | Primary | Fallback | Примечание |
|------|---------|----------|------------|
| Image gen/edit | OpenAI Images API (`gpt-image-1`) | Fal/Replicate Flux | Текст на картинке, inpaint |
| I2V / short clip | Fal.ai или Replicate (Runway/Kling workflows) | Luma API | 4–8 s на сцену |
| TTS | ElevenLabs | OpenAI TTS | Brand voice_id в BrandKit |
| Transcribe | OpenAI Whisper API | Deepgram | RU/EN subs |
| Vision QA | GPT-4o / совместимый vision | Локальная LLaVA (phase 2+) | Score vs brief |
| Orchestration proxy | **Fal.ai** | Replicate | Единый webhook + billing |
| Compose | **ffmpeg локально** | — | Не отправлять master в cloud |

### Не в v1

- Midjourney (нет официального API)
- Полный 60s one-shot T2V (только multi-scene)
- Voice clone без artifact consent
- Sora / закрытые betas без стабильного API

---

## Архитектура

```text
Clients (Desktop / SDK / Web)
        ↓
POST /api/media/*  +  agent tools (generate_image, render_video, …)
        ↓
MediaJobService (async) ──webhook──► Fal / Replicate / OpenAI
        ↓
MediaAssetStore (data/media/{project_id}/)
        ↓
compose_media (ffmpeg) → deliverables + eval verify
```

### Сущности данных

- `CreativeBrief` — цель, аудитория, duration, CTA, constraints
- `BrandKit` — colors, fonts, logos, voice_id, music_mood
- `Storyboard` — scenes[] с visual_prompt, voiceover, duration_sec
- `MediaJob` — provider, status, cost_usd, webhook
- `MediaAsset` — path, mime, scene_id, seed, metadata
- `CostLedger` — run_id, line items, cap enforcement

JSON Schema: `data/media/schemas/`.

### TaskType (Фаза 1)

Добавить `TaskType.creative_media` и routing:

- Director / QA → strong cloud LLM + vision
- Draft storyboard → cheaper model

### Agent tools v1 (контракт)

См. [`data/media/tools_v1.json`](../data/media/tools_v1.json).

| Tool | Sync/async | Risk |
|------|------------|------|
| `generate_image` | sync (timeout 120s) | confirm if cost > threshold |
| `edit_image` | sync | confirm |
| `render_video` | **async** (job_id) | confirm always cloud |
| `tts_generate` | sync | confirm |
| `transcribe_media` | sync | safe |
| `compose_media` | sync (ffmpeg) | safe |
| `vision_qa_media` | sync | safe |
| `list_media_assets` | sync | safe |
| `estimate_media_cost` | sync | safe (pre-flight) |

### Multi-agent preset «studio»

| Agent | task | tools |
|-------|------|-------|
| creative-director | storyboard | read, LLM |
| visual-artist | scenes | generate_image, render_video |
| sound-designer | audio | tts_generate, compose_media |
| editor | timeline | compose_media, list_media_assets |
| qa-critic | gate | vision_qa_media |

Orchestration через существующий `spawn_agent` + template `studio-pack` (Фаза 4).

### Безопасность

- `TERMIT_MEDIA_MAX_COST_USD` — hard stop per run
- `estimate_media_cost` до confirm
- Blocklist: NSFW, non-consensual deepfake, trademark prompts без license
- Audit: `data/media/audit.jsonl` (provider, usd, run_id)
- Secrets только `.env`, не в workspace git

### Хранение

- Root: `TERMIT_MEDIA_STORAGE` (default `./data/media`)
- Layout: `{project_id}/assets/`, `{project_id}/jobs/`, `{project_id}/exports/`
- Intermediate TTL: 7 days (config)
- Finals → `deliverables/` assignment или project exports

### API surface (Фаза 1+)

| Method | Path | Назначение |
|--------|------|------------|
| POST | `/api/media/jobs` | Создать job |
| GET | `/api/media/jobs/{id}` | Статус |
| GET | `/api/media/assets` | Список по run/project |
| POST | `/api/media/estimate` | Pre-flight cost |
| GET | `/api/media/brand-kits/{id}` | Brand kit |

SSE: события `media.job.progress` в agent run stream.

### RBAC

- Permission `media:cloud` — cloud providers
- Permission `media:compose` — ffmpeg
- Role `viewer` — только list/preview, без generate

---

## Последствия

### Плюсы

- Единый UX с agent runs, eval, Desktop timeline
- Cost control и audit в одном месте
- Hybrid снижает счёт vs full-cloud montage

### Минусы

- 6–10 недель до полного studio UI
- Зависимость от внешних API и rate limits
- Нужен ffmpeg на хосте агента

### Риски

| Риск | Митигация |
|------|-----------|
| Vendor lock | `MediaProvider` interface; Fal primary |
| Drift персонажа между сценами | Hero frame + I2V; vision QA retry |
| Дорогой runaway | estimate + cap + confirm |
| Долгие jobs | async + SSE, не блокировать loop |

---

## Критерии выхода Фазы 0

- [x] ADR принят
- [x] Use cases и non-goals задокументированы
- [x] JSON schemas brief + storyboard
- [x] `tools_v1.json` + eval registry `eval_scenarios_media.json`
- [x] Skill outline `data/skills/media-studio/`
- [x] `.env.example` ключи (закомментированы)
- [x] Unit-тест `tests/test_media_studio_phase0.py`

**Следующий шаг:** Фаза 1 — Image MVP (`MediaAssetStore`, `generate_image`, один provider).

---

## Отклонённые варианты

1. **Только MCP** — оставлен как escape hatch (`mcp_invoke`), не как core.
2. **Cloud-only montage** — отклонено из-за cost и latency.
3. **Встроить DaVinci/After Effects GUI** — out of scope; только ffmpeg/Remotion scripts.
