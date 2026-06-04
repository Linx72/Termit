# Media Studio — Фаза 0 (Discovery)

**Срок:** 3–5 рабочих дней  
**Статус:** завершена (артефакты в репозитории)  
**ADR:** [`MEDIA_STUDIO_ADR_RU.md`](MEDIA_STUDIO_ADR_RU.md)

---

## Цель

Зафиксировать scope, provider strategy, контракт tools v1 и eval до написания `media_*` сервисов.

---

## Use cases (in scope v1–v2)

| ID | Сценарий | Выход | Приоритет |
|----|----------|-------|-----------|
| UC1 | App icon / logo 512×512 | PNG + 2 variants | P0 |
| UC2 | Social banner 1200×628 | PNG | P0 |
| UC3 | Product screenshot → 5s motion | MP4 (I2V) | P1 |
| UC4 | 30–45s promo из storyboard | MP4 16:9 + 9:16 | P1 |
| UC5 | Slideshow + VO + subs | MP4 + SRT | P1 |
| UC6 | Brand kit reuse (colors, logo) | Consistent scenes | P1 |
| UC7 | Cost estimate before render | USD breakdown | P0 |
| UC8 | Human approve before deliverables | Gate in Desktop | P2 |

## Non-goals (явно не делаем в v1)

- Полнометражное кино, live stream
- Midjourney pipeline без API
- Voice clone без файла согласия в project
- Встроенный NLE (timeline UI как DaVinci)
- GPU training custom LoRA (отдельный трек)

---

## Решения Discovery (чеклист)

| # | Вопрос | Решение |
|---|--------|---------|
| 1 | Cloud vs local default | **Hybrid studio** (см. ADR) |
| 2 | Единая точка GPU proxy | **Fal.ai** primary, Replicate fallback |
| 3 | Images primary | **OpenAI Images** + Fal Flux для A/B |
| 4 | Short video | **I2V** (hero frame → clip), не длинный T2V |
| 5 | Монтаж | **ffmpeg на хосте Termit** |
| 6 | TTS | **ElevenLabs** primary |
| 7 | Subs | **Whisper API** |
| 8 | QA | **Vision LLM** + технические проверки ffmpeg |
| 9 | Budget default | **$25/run**, hard cap `TERMIT_MEDIA_MAX_COST_USD` |
| 10 | Human gate | **Обязателен** для `cost > $10` или `duration > 30s` |
| 11 | Storage | `./data/media` + optional S3 (phase 5) |
| 12 | Интеграция | Native tools + `/api/media/*`, MCP — optional |

---

## Подготовка аккаунтов (до Фазы 1)

```text
[ ] OPENAI_API_KEY          — images, TTS, whisper, vision QA
[ ] FAL_KEY                 — I2V / Flux workflows
[ ] REPLICATE_API_TOKEN     — fallback proxy
[ ] ELEVENLABS_API_KEY      — voiceover
[ ] ffmpeg в PATH           — compose_media
[ ] Webhook URL HTTPS       — async jobs (staging/prod)
```

Лицензии:

- Music: Epidemic/Artlist **или** royalty-free pack в `data/media/library/` (не генерировать Suno для commercial без legal review).
- Voice clone: только с `data/media/consent/{id}.json`.

---

## Контент-политика (кратко)

**Запрещено генерировать:** NSFW, violence gore, non-consensual likeness, instructions для illegal acts.

**Требует confirm:** political ads, medical claims, trademarked characters.

**Логирование:** каждый cloud call → `data/media/audit.jsonl` (без сырого prompt в production logs если `TERMIT_MEDIA_REDACT_PROMPTS=true`).

---

## Eval v1 (реестр)

Файл: [`data/eval_scenarios_media.json`](../data/eval_scenarios_media.json)

| ID | Что проверяет | Runner (сейчас) |
|----|---------------|-----------------|
| MS1 | Storyboard schema valid | `media_schema` |
| MS2 | Brief schema valid | `media_schema` |
| MS3 | Cost estimate stub | `media_stub` |
| MS4–MS10 | Agent E2E (phase 1+) | `media_agent` (planned) |

Фаза 0: прогоняются только **MS1–MS2** через `tests/test_media_studio_phase0.py`.

---

## Deliverables Фазы 0

| Артефакт | Путь |
|----------|------|
| ADR | `docs/MEDIA_STUDIO_ADR_RU.md` |
| Roadmap | `docs/MEDIA_STUDIO_ROADMAP_RU.md` |
| Tools contract | `data/media/tools_v1.json` |
| Schemas | `data/media/schemas/*.json` |
| Examples | `data/media/examples/*.json` |
| Eval registry | `data/eval_scenarios_media.json` |
| Skill outline | `data/skills/media-studio/SKILL.md` |
| Env template | `.env.example` (секция Media) |
| Tests | `tests/test_media_studio_phase0.py` |

---

## Exit criteria ✅

- ADR статус «Принято»
- Все deliverables в таблице существуют
- `python3 -m unittest tests.test_media_studio_phase0 -q` — OK
- Нет секретов в git

**Handoff в Фазу 1:** реализовать `MediaAssetStore` + `generate_image` + config keys в `app/core/config.py`.
