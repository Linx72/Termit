# Локальный SDXL через ComfyUI в Termit Media Studio

Связано: [`MEDIA_STUDIO_ADR_RU.md`](MEDIA_STUDIO_ADR_RU.md), [`MEDIA_STUDIO_ROADMAP_RU.md`](MEDIA_STUDIO_ROADMAP_RU.md)

## Назначение

Локальная генерация изображений **Stable Diffusion XL** без облачных API. Termit вызывает ComfyUI sidecar через provider `comfy` (alias `sdxl`) в tool `generate_image` и API `POST /api/media/generate-image`.

## Быстрый старт

```bash
# 1. Установка ComfyUI + SDXL weights (~6.5 GB)
./scripts/setup_comfy_sdxl.sh

# 2. Запуск sidecar
./scripts/start_comfy_sidecar.sh

# 3. Проверка
./scripts/check_comfy_health.sh

# 4. Termit
export TERMIT_MEDIA_ENABLED=true
export TERMIT_MEDIA_IMAGE_PROVIDER=comfy
./scripts/restart_server.sh

# 5. Smoke
curl -X POST http://127.0.0.1:8765/api/media/generate-image \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Termit logo minimal dark blue","width":1024,"height":1024,"provider":"comfy"}'
```

## Env

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `TERMIT_MEDIA_ENABLED` | `false` | Включить Media Studio |
| `TERMIT_MEDIA_IMAGE_PROVIDER` | `openai` | `comfy` / `sdxl` / `openai` / `stub` |
| `TERMIT_MEDIA_COMFY_URL` | `http://127.0.0.1:8188` | URL ComfyUI |
| `TERMIT_MEDIA_COMFY_WORKFLOW` | `./data/media/workflows/sdxl_t2i_api.json` | Workflow API |
| `TERMIT_MEDIA_COMFY_CHECKPOINT` | `sd_xl_base_1.0.safetensors` | Имя файла в `models/checkpoints/` |
| `TERMIT_MEDIA_COMFY_TIMEOUT_SEC` | `180` | Таймаут ожидания PNG |
| `TERMIT_COMFY_DIR` | `../ComfyUI` | Каталог установки (скрипты) |

## Архитектура

```text
Agent (Hermes/vLLM/Ollama tool loop)
    → generate_image(provider=comfy)
    → MediaGenerationService
    → ComfyImageProvider (HTTP /prompt, /history, /view)
    → ComfyUI :8188 + SDXL checkpoint
    → data/media/{project_id}/*.png
```

## Железо

| Платформа | Ожидание |
|-----------|----------|
| Apple Silicon (MPS) | Работает, ~30–90 с/кадр 1024² |
| NVIDIA CUDA | Рекомендуется для storyboard, ~3–10 с/кадр |
| CPU only | Очень медленно, не для prod |

Remote GPU: SSH tunnel `ssh -L 8188:127.0.0.1:8188 user@gpu-host` + `TERMIT_MEDIA_COMFY_URL=http://127.0.0.1:8188`.

## Hybrid routing

| Задача | Provider |
|--------|----------|
| Dev / offline / приватность | `comfy` |
| Текст на картинке, inpaint | `openai` |
| CI / без GPU | `stub` |

## Cursor + TermitPro

1. Rule: `.cursor/rules/media-sdxl-local.mdc`
2. Skill: `data/skills/media-studio/SKILL.md`
3. Агенты: `creative-artist`, `studio-director` в `data/agent_templates.json`
4. Desktop: Media Studio panel → provider «Local SDXL»

## Тесты

```bash
.venv/bin/python -m unittest tests.test_media_provider_comfy tests.test_media_generation -q
```

Eval: сценарий `MS12` (provider wired).

## Troubleshooting

| Симптом | Решение |
|---------|---------|
| `ComfyUI недоступен` | `./scripts/start_comfy_sidecar.sh`, `tail -f data/ops/comfy_sidecar.log` |
| Checkpoint not found | `./scripts/setup_comfy_sdxl.sh` |
| Timeout 180s | Уменьшите размер или увеличьте `TERMIT_MEDIA_COMFY_TIMEOUT_SEC` |
| OOM на Mac | Закройте другие GPU-процессы; используйте 768² |
