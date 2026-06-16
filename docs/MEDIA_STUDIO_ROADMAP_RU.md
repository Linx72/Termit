# Media Studio — roadmap (phases 0–6)

Связано: [`MEDIA_STUDIO_ADR_RU.md`](MEDIA_STUDIO_ADR_RU.md)

| Фаза | Статус | Exit |
|------|--------|------|
| 0 Discovery | ✅ | ADR, schemas, eval registry |
| 1 Image MVP | ✅ | `generate_image`, API, `creative-artist` |
| 2 Post-production | ✅ | `compose_media`, TTS, Whisper |
| **3 Animation** | ✅ | `export_gif`, stub I2V (ffmpeg zoompan) |
| **4 Studio pack** | ✅ | `render_video`, `wait_media_job`, `run_storyboard`, `studio-director` |
| **5 Desktop UX** | ✅ | `MediaStudioPanel`, `mediaOps.ts`, brand kits API |
| **6 Eval** | ✅ | runners `media_schema`, `media_stub`, `media_agent`; MS1–MS9 |

## API surface (full)

| Method | Path |
|--------|------|
| POST | `/api/media/generate-image` |
| POST | `/api/media/compose` |
| POST | `/api/media/tts` |
| POST | `/api/media/transcribe` |
| POST | `/api/media/render-video` |
| GET | `/api/media/jobs/{id}` |
| POST | `/api/media/export-gif` |
| POST | `/api/media/run-storyboard` |
| GET | `/api/media/brand-kits` |
| GET | `/api/media/assets` |

## Env

```env
TERMIT_MEDIA_ENABLED=true
TERMIT_FFMPEG_PATH=ffmpeg
FAL_KEY=   # optional; local stub I2V by default
TERMIT_MEDIA_I2V_PROVIDER=stub
```

## Tests

```bash
.venv/bin/python -m unittest tests.test_media_studio_phase0 tests.test_media_generation tests.test_media_compose tests.test_media_jobs -q
python3 -m unittest discover -s tests -p 'test_eval*.py' -q  # includes MS scenarios via EvalService
```

## Future (optional)

- Fal I2V with public image URL upload
- OTEL spans per media tool
- Lottie export path
- ~~Human approve gate in Desktop before cloud spend~~ — Desktop confirm UI on HTTP 428 (0.3.9)
