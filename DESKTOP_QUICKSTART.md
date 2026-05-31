# Termit Desktop — быстрый старт

Своё приложение **Termit** + свой AI (Ollama). **Cursor не нужен.**

## Один скрипт (разработка)

```bash
cd /path/to/Termit
chmod +x scripts/run_termit_stack.sh scripts/package_desktop.sh
./scripts/run_termit_stack.sh
```

Поднимает Ollama (если есть `.tools/ollama`), API на `:8765` и desktop (`npm run dev`).

Только сервер:

```bash
./scripts/run_termit_stack.sh --server-only
```

## Первый запуск в приложении

1. **Choose repo** — папка клона Termit (где `app/` и `.venv`).
2. Включите **Start Termit server on app launch** (опционально).
3. **Choose folder** — workspace с вашим кодом.
4. **Connect** (или включите **Connect on launch**).
5. Вкладки: Chat, Composer, Editor, Tasks, Agents.

## Собрать .app (macOS)

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
