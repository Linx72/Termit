# Termit Desktop — быстрый старт

Своё приложение **Termit** + свой AI (Ollama). **Cursor не нужен.**

## Полная автоматическая настройка

```bash
cd /path/to/Termit
chmod +x scripts/*.sh
./scripts/do_all_setup.sh
```

Скрипт: venv, тесты, Node в `.tools/`, сборка SDK и desktop, push на GitHub (если SSH настроен).

## Запуск API (без desktop)

**Рекомендуется на macOS — LaunchAgent (сервер при входе в систему):**

```bash
cd /path/to/Termit
./scripts/install_launch_agent.sh
# или: TERMIT_INSTALL_LAUNCH_AGENT=1 ./scripts/do_all_setup.sh
```

Логи LaunchAgent: `.tools/termit-launchd.log`, `.tools/termit-launchd.err.log`.

**Вручную (разработка или без LaunchAgent):**

```bash
cd /path/to/Termit
./scripts/start_server.sh          # если порт занят и сервер жив — просто сообщит и выйдет
./scripts/restart_server.sh        # остановить :8765 и поднять заново в фоне
./scripts/stop_server.sh           # освободить порт
```

Проверка моделей Ollama:

```bash
./scripts/check_ollama_models.sh
```

Не используйте `uvicorn ... on http://...` — нужны флаги `--host` и `--port`.

## Один скрипт (разработка)

```bash
cd /path/to/Termit
./scripts/run_termit_stack.sh
```

Поднимает Ollama (если есть `.tools/ollama`), API на `:8765` и desktop (`npm run dev`).

Только сервер:

```bash
./scripts/run_termit_stack.sh --server-only
```

## Первый запуск в приложении

1. **Choose repo** — путь к папке клона Termit (где `app/` и `.venv`), через встроенную модалку.
2. Включите **Start Termit server on app launch** (опционально).
3. **Choose folder** — путь к workspace с вашим кодом, через ту же модалку.
4. **Connect** (или включите **Connect on launch**).
5. Вкладки: Chat, Composer, Editor, Tasks, Agents.

### Единый UI-поток (desktop + web)

- Для выбора файлов/папок (`Open file`, `@file`, `@folder`, `Composer @file`) используется встроенная модалка выбора.
- Для коротких вводов (`@symbol`, `@web`, path inputs) используется встроенная модалка ввода.
- `window.prompt` и platform-specific picker ветки в ключевых пользовательских потоках не используются.
- `runtimeMode` (`auto|desktop|web`) влияет на server-control сценарии, а не на различия UX.

## Собрать .app / .dmg (macOS)

```bash
./scripts/generate_desktop_icon.sh
cd clients/termit-desktop
npm run package:dmg
open release/*.dmg
```

Без подписи Apple сборка может не открыться двойным кликом. Обход для локальной разработки:

```bash
xattr -cr release/mac-arm64/Termit.app
# или: System Settings → Privacy & Security → Open Anyway
```

Подпись и notarization для распространения — отдельный шаг (не входит в MVP).

Альтернатива без DMG:

```bash
./scripts/package_desktop.sh
open clients/termit-desktop/release/mac-arm64/Termit.app
```

## Модели

- Установите Ollama и модели из `.env` (`ollama pull deepseek-coder` и т.д.).
- Finetune-адаптеры появятся в списке моделей после `POST /api/finetune/adapters`.
- **Repo profile** в сайдбаре — маршрутизация по части репозитория.

## Другой компьютер

```bash
git clone git@github.com:<you>/Termit.git
cd Termit
./scripts/setup_new_machine.sh
./scripts/run_termit_stack.sh
```

См. [SYNC_WORKFLOW.md](SYNC_WORKFLOW.md) и [GITHUB_SETUP_RU.md](GITHUB_SETUP_RU.md) (первый push).

## Проверка

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/api/providers/status
```
