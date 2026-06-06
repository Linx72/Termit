# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-05T10:54:07Z

**Причина:** session stop

**Последний checkpoint:** [`20260605-105407_6e35b420-fd69-4acb-8707-.md`](checkpoints/20260605-105407_6e35b420-fd69-4acb-8707-.md)

## Сводка
- **Готово.** Полная пересборка выполнена: - `./scripts/package_termit_shell.sh` — frontend + Swift + bundle - [`TermitShell.app`](file:///Users/amoros/Projects/Termit/clients/termit-shell/release/TermitShell.app) создан и **запущен** - Backend `:8765` — `{"status":"ok"}` - Тесты…
- **Исправлено.** Чёрный экран был из‑за того, что CSS загружался, а JS-модули — нет: `loadHTMLString` в WKWebView не запускает ES modules. **Что изменилось:** - Renderer копируется в `~/Library/Application Support/TermitShell/renderer-cache/` - `index.html` нормализуется (без `cr…
- ## Что главное В Termit три слоя, не два «приложения»: | Что | Роль | Где | |-----|------|-----| | **Termit (сервер)** | Ядро: API, агенты, роутинг моделей | `uvicorn` на `:8765` | | **Termit Desktop (UI)** | Интерфейс: чат, задачи, агенты | React в [`clients/termit-desktop`](fi…
- ## Коротко **Можно было** — но сознательно разделили: **сервер (Python)** и **клиент (UI + Shell)**. Это не «два приложения ради усложнения», а разные роли. --- ## Почему так сделано **1. Разный стек и жизненный цикл** - **Termit server** — Python, FastAPI, Ollama, агенты, tools…

## Файлы сессии
- `/Users/amoros/Projects/Termit/clients/termit-shell/Sources/TermitShell/main.swift`
- `/Users/amoros/Projects/Termit/scripts/package_termit_shell.sh`
- `/Users/amoros/Projects/Termit/clients/termit-shell/release/TermitShell.app/Contents/Resources/renderer/index.html`
- `/Users/amoros/Projects/Termit/tests/test_termit_shell_runtime_smoke.py`
- `/Users/amoros/Projects/Termit/clients/termit-desktop`
- `/Users/amoros/Projects/Termit/scripts/run_termit_shell.sh`
- `/Users/amoros/Projects/Termit/clients/termit-desktop/src/App.tsx`
- `/Users/amoros/Projects/Termit/clients/termit-desktop/vite.config.ts`
- `/Users/amoros/Projects/Termit/clients/termit-desktop/index.html`
- `/Users/amoros/Projects/Termit/clients/termit-desktop/src/main.tsx`
- `/Users/amoros/Projects/Termit/clients/termit-desktop/src/settings.ts`
- `/Users/amoros/Projects/Termit/clients/termit-shell/release/TermitShell.app/Contents/Resources/renderer/assets/index-C4O9FpZf.js`
- `/Users/amoros/.cursor/projects/Users-amoros-Projects-Termit/terminals/946667.txt`
- `/Users/amoros/Projects/Termit/clients/termit-desktop/electron/main.ts`
- `/Users/amoros/Projects/Termit/clients/termit-shell/README.md`
- `/Users/amoros/Projects/Termit/README.md`
- `/Users/amoros/Projects/Termit/clients/termit-desktop/README.md`
- `/Users/amoros/Projects/Termit`
- `/Users/amoros/Projects/Termit/START_HERE_RU.md`
- `/Users/amoros/Projects/Termit/scripts/run_termit_stack.sh`

## Открытые задачи
- [ ] Заполните вручную или через compact-chat после крупной сессии
