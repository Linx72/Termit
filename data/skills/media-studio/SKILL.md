---
name: media-studio
description: >-
  Termit Media Studio: creative brief, storyboard, hybrid cloud+ffmpeg pipeline,
  cost cap, vision QA, deliverables. Use for images, short video, promo, social assets.
---

# Media Studio (Termit)

**Фаза:** 0 — контракт и workflow; tools реализуются в Фазах 1–4.

## Когда применять

- Пользователь просит картинку, баннер, иконку, анимацию, promo-ролик
- Нужен storyboard, озвучка, субтитры, экспорт 16:9 / 9:16
- Упоминаются Runway, Fal, ElevenLabs, ffmpeg в контексте Termit

## Северная звезда

Бриф → `storyboard.json` → сцены (image → I2V) → TTS → `compose_media` → QA → `deliverables/`.

## Обязательный порядок

1. Прочитать или создать **CreativeBrief** (`data/media/schemas/creative_brief.schema.json`).
2. Подключить **BrandKit** если есть `brand_kit_id`.
3. Вызвать **`estimate_media_cost`** перед cloud-рендером (когда tool доступен).
4. Если `max_cost_usd` превышен — сократить сцены или упростить `render_mode`.
5. Director: storyboard с `scene_id`, `duration_sec`, `render_mode`.
6. Visual: `generate_image` → `vision_qa_media` (retry max 2 per scene).
7. Motion: `render_video` + `wait_media_job` только для `image_to_video` / `text_to_video` (Phase 4).
8. Sound: `tts_generate` по чанкам voiceover; `confirmed=true` если cost > threshold.
9. Editor: `compose_media` с timeline JSON (`clips`, `audio_asset_id`, `preset`); ffmpeg локально.
10. Subs: `transcribe_media` → SRT asset; опционально burn-in через timeline `subtitle_asset_id`.
11. Human approve если `require_human_approve` или cost > $10.
12. Копировать finals в assignment `deliverables/` + journal.

## Timeline (compose_media)

Файл: `data/media/examples/timeline.slideshow.example.json`

```json
{
  "preset": "youtube_16x9",
  "crossfade_sec": 0.3,
  "clips": [{"asset_id": "...", "duration_sec": 3}],
  "audio_asset_id": "...",
  "subtitle_asset_id": "..."
}
```

## Render modes (по сцене)

| mode | Действие |
|------|----------|
| `image_only` | Только PNG |
| `ken_burns` | PNG + ffmpeg pan/zoom |
| `image_to_video` | PNG → I2V 4–8s |
| `text_to_video` | T2V только если нет референса |
| `remotion_template` | End card / data-driven |

## Cloud (studio default)

- Images: OpenAI Images; A/B Flux via Fal
- I2V: Fal/Replicate
- TTS: ElevenLabs
- Subs: Whisper API
- QA: vision model vs criteria из brief

## Локально всегда

- `compose_media` — ffmpeg
- Проверка: `ffprobe` duration, resolution, audio loudness

## Запреты

- NSFW, deepfake без consent
- Voice clone без `data/media/consent/`
- Один 60s T2V shot вместо multi-scene
- Текст внутри generative video (использовать overlay)

## Артефакты

- ADR: `docs/MEDIA_STUDIO_ADR_RU.md`
- Tools: `data/media/tools_v1.json`
- Examples: `data/media/examples/`

## Verify (после Фазы 1+)

```bash
python3 -m unittest tests.test_media_studio_phase0 -q
# будущее: tests.test_media_generation
```
