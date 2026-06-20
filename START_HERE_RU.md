# Termit — начните здесь

Своё приложение **Termit** + свой AI (Ollama). Cursor не нужен.

## 1. Один раз: настройка

```bash
cd /path/to/Termit
chmod +x scripts/*.sh
./scripts/do_all_setup.sh
```

## 2. Сервер API (порт 8765) — по умолчанию LaunchAgent

**Рекомендуется (macOS): API поднимается при каждом входе в систему:**

```bash
./scripts/install_launch_agent.sh
# или вместе с полной настройкой:
TERMIT_INSTALL_LAUNCH_AGENT=1 ./scripts/do_all_setup.sh
```

Логи: `.tools/termit-launchd.log` и `.tools/termit-launchd.err.log` в корне репозитория.

**Альтернатива — вручную в терминале (вкладка всегда открыта):**

```bash
./scripts/start_server.sh
```

**Проверка моделей Ollama** (из `.env.example`):

```bash
./scripts/check_ollama_models.sh
```

Проверка: http://127.0.0.1:8765/health → `{"status":"ok"}`

Если `Address already in use` → `./scripts/restart_server.sh`  
Если браузер `ERR_CONNECTION_REFUSED` → сервер не запущен, см. выше.

## 3. Ollama (модели)

```bash
./scripts/start_ollama_local.sh   # или системный ollama serve
ollama pull termit-core-ft
# Рекомендуемая ladder (14B base): ./scripts/upgrade_model_ladder_phase_a.sh
# Teacher (stage-1 finetune only):
ollama pull deepseek-coder
ollama pull nomic-embed-text      # для semantic retrieval
# профиль app/ → ollama:termit-core-ft (alias над deepseek-coder до Stage1 finetune):
./scripts/check_ollama_models.sh --create-missing
```

## 4. Приложение Termit (desktop)

```bash
open clients/termit-desktop/release/mac-arm64/Termit.app
# или разработка:
./scripts/run_termit_stack.sh
```

В приложении:

1. **Choose repo** → путь к папке клона Termit (через встроенную модалку)  
2. **Start server on launch** (опционально)  
3. **Choose folder** → путь к вашему workspace (через встроенную модалку)  
4. **Connect** — индикатор API / Ollama в сайдбаре  

UX parity: потоки выбора файлов/папок и коротких вводов (`@symbol`, `@web`) идут через встроенные модалки; `window.prompt` в ключевых пользовательских потоках не используется.

## 5. GitHub (несколько Mac)

```bash
./scripts/setup_github_ssh.sh
# ключ → https://github.com/settings/keys
# создать репо Termit на GitHub
./scripts/first_push.sh
```

Ежедневно: `./scripts/sync_start.sh` → работа → `./scripts/sync_finish.sh "описание"`

## 6. Semantic поиск по коду

В `.env`:

```bash
TERMIT_RETRIEVAL_MODE=semantic
TERMIT_RETRIEVAL_EMBED_MODEL=nomic-embed-text
```

Переиндекс: UI или `POST /api/retrieval/reindex`. Без Ollama embeddings — fallback на keyword.

## 6a. Model ladder (coding)

Док: [`docs/MODEL_LADDER_RU.md`](docs/MODEL_LADDER_RU.md).

```bash
./scripts/upgrade_model_ladder_phase_a.sh   # pull 14B + recreate termit-core-ft
# В .env: TERMIT_DUAL_PASS_ENABLED=true, OPENAI_COMPAT_API_KEY для cloud validator
# Verify: scripts/swe_eval_gate.py (SWE1–5), do_all_verify.sh шаг 2c
```

## 7. Кроссплатформа (iOS / macOS / Windows / Android)

Приложения и игры — **атомарными шагами** (один шаг → одна проверка):

```bash
curl -s http://127.0.0.1:8765/api/dev/cross-platform/decompose \
  -H 'Content-Type: application/json' \
  -d '{"goal":"Flutter MVP для iOS и Android","stack_id":"flutter"}'
```

- **Desktop:** пресеты Flutter / Swift / Unity / MAUI над полем чата  
- **VS Code:** `Termit: Cross-Platform Task` в Command Palette  
- **SDK:** `runAtomicDevWorkflow()` из `@termit/client`  
- **Док:** [CROSS_PLATFORM_DEV_RU.md](docs/CROSS_PLATFORM_DEV_RU.md)

## 8. Первый Composer run за ~10 минут

1. Запустите API (`./scripts/start_server.sh` или LaunchAgent) и Ollama с моделью из `.env.example`.
2. Откройте **Termit desktop** или VS Code extension → **Connect** (индикатор API зелёный).
3. **Choose folder** — корень репозитория с кодом (через встроенную модалку).
4. Вкладка **Composer** → **Add file** (или `@file` в chat) → опишите задачу, например: «Добавь unit-тест для функции X».
5. Дождитесь diff preview → **Apply** (или Apply all).
6. Опционально: вкладка **Agents** → запустите agent run с tool loop — timeline обновляется через **SSE** (`/api/agents/runs/{id}/stream`).

Post-patch verify (авто `pytest`/`npm test` при `TERMIT_AGENT_VERIFY_AFTER_PATCH=true`):

```bash
# .env
TERMIT_AGENT_VERIFY_AFTER_PATCH=true
# TERMIT_AGENT_VERIFY_CMD=  # пусто = авто по типу репо
```

## Шпаргалка скриптов

| Скрипт | Назначение |
|--------|------------|
| `start_server.sh` | Сервер в foreground |
| `restart_server.sh` | Перезапуск в фоне |
| `stop_server.sh` | Освободить :8765 |
| `run_termit_stack.sh` | Ollama + API + desktop dev |
| `package_desktop.sh` | Собрать Termit.app |
| `install_launch_agent.sh` | **По умолчанию:** API при входе в macOS (LaunchAgent) |
| `check_ollama_models.sh` | Модели из `.env`, routing profiles; `--create-missing` для `termit-core-ft` |
| `do_all_automatic.sh` | Полный авто-режим: .env, LaunchAgent, crontab, schedulers |
| `smoke_http.sh` | Curl smoke `:8765` (health, readiness, agent metrics) |
| `smoke_all.sh` | Тесты + platform e2e + smoke HTTP (единый контур Фазы 0) |
| `training_loop_week2.sh` | Export signals → job → KPI dashboard (Фаза 4) |
| `release_smoke.sh` | То же, что `smoke_all.sh` (alias) |

## 9. Автоматизация (do_all_automatic + отключение в Desktop)

```bash
TERMIT_SKIP_OLLAMA_CHECK=1 ./scripts/do_all_automatic.sh
```

В **Termit Desktop** → sidebar → **«Автоматизация сервера»** — включить/выключить Stage1, daily improvement, crontab и др. без правки `.env` вручную.

Промпт для агентов: [AUTOMATION_TASK_PROMPT_RU.md](AUTOMATION_TASK_PROMPT_RU.md). Skill: `.cursor/skills/termit-automation/SKILL.md`.

Подробнее: [DESKTOP_QUICKSTART.md](DESKTOP_QUICKSTART.md), [GITHUB_SETUP_RU.md](GITHUB_SETUP_RU.md), [SYNC_WORKFLOW.md](SYNC_WORKFLOW.md).

## 10. Media Studio (картинки, анимация, видео)

**Фазы 0–6 Media Studio реализованы** — включение: `TERMIT_MEDIA_ENABLED=true`, `ffmpeg` в PATH.

| Документ | Назначение |
|----------|------------|
| [docs/MEDIA_STUDIO_ADR_RU.md](docs/MEDIA_STUDIO_ADR_RU.md) | Архитектура: hybrid studio, провайдеры, tools |
| [docs/MEDIA_STUDIO_PHASE0_RU.md](docs/MEDIA_STUDIO_PHASE0_RU.md) | Use cases, решения, чеклист аккаунтов |
| [docs/MEDIA_STUDIO_ROADMAP_RU.md](docs/MEDIA_STUDIO_ROADMAP_RU.md) | Фазы 1–6 |

Проверка Фазы 0:

```bash
python3 -m unittest tests.test_media_studio_phase0 -q
```

Ключи API — секция **Media Studio** в `.env.example`. Skill: `data/skills/media-studio/SKILL.md`. Agent templates: `creative-artist`, `studio-director`. Desktop: панель **Media Studio** в настройках чата.

## 11. AutoCheckPoint (длинные чаты Cursor)

Память сессии: `.cursor/memory/ACTIVE.md`, снимки в `.cursor/memory/checkpoints/`. Порог **100 000 токенов** перед compaction — `TERMIT_CHECKPOINT_TOKEN_THRESHOLD`. Подробнее: [docs/AUTOCHECKPOINT_RU.md](docs/AUTOCHECKPOINT_RU.md). Hooks: `.cursor/hooks.json`.

## 12. Nightly flaky gates (операционная дисциплина)

Для nightly quality-gates есть отдельный регрессионный контроль flaky suite (`tests.test_agents_api`, `tests.test_platform_e2e`) с временными override по TTL.

- Документация override: [docs/FLAKY_WATCH_OVERRIDES_RU.md](docs/FLAKY_WATCH_OVERRIDES_RU.md)
- Runbook инцидента (первые 10 минут): [docs/NIGHTLY_FLAKY_GATE_RUNBOOK_RU.md](docs/NIGHTLY_FLAKY_GATE_RUNBOOK_RU.md)
- Конфиг override: `data/flaky_watch_gate_overrides.json`
