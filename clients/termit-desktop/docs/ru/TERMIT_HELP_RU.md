# Termit — справка пользователя

Версия документа: 0.3.2  
Язык: русский

---

## 1. Что такое Termit

Termit — локальный AI-оркестратор для написания и сопровождения кода. Состоит из:

- **API-сервера** (FastAPI, порт 8765) — chat, composer, tasks, agents, eval, finetune.
- **Ollama** — локальные LLM-модели без облачных ключей.
- **Desktop-приложения Termit** — клиент с Chat, Composer, Editor, Plan, Terminal, Agents, Online.
- **Agent tool loop** — агент читает файлы, правит код, запускает verify, отчитывается.

Cursor и платные облачные IDE **не требуются**.

---

## 2. Быстрая настройка

### 2.1. Репозиторий Termit

Выберите папку клона проекта (содержит `app/`, `scripts/`, `.venv`):

```
/Users/you/Projects/Termit
```

### 2.2. API Termit

URL по умолчанию: `http://127.0.0.1:8765`

Запуск сервера:

- macOS LaunchAgent: `./scripts/install_launch_agent.sh`
- Вручную: `./scripts/start_server.sh`
- Из desktop: «Запускать сервер Termit при старте приложения»

Проверка: откройте в браузере `/health` — ответ `{"status":"ok"}`.

### 2.3. Ollama и модели

```bash
ollama pull deepseek-coder
ollama pull qwen2.5-coder
ollama pull nomic-embed-text
```

Проверка: `./scripts/check_ollama_models.sh`

### 2.4. Workspace

Папка с **вашим кодом** (может отличаться от репозитория Termit). Retrieval и apply_patch работают относительно workspace.

### 2.5. Connect

В sidebar нажмите **Подключить**. Индикаторы: API online, Ollama ok.

---

## 3. Интерфейс desktop

### 3.1. Вкладки

| Вкладка | Назначение |
|---------|------------|
| Chat | Диалог со streaming, @файлы, queue task |
| Composer | Мультифайловые правки, diff preview, apply |
| Editor | Monaco-редактор, tab completion |
| Plan | План без кода → Build в Composer |
| Terminal | Команды verify (pytest, git, npm) |
| Tasks | Жизненный цикл plan/execute/verify/report |
| Agents | Agent runs, SSE timeline, resume |
| Online | Shared runs, heavy jobs (eval) |
| Справка | Эта документация и PDF локально |

### 3.2. Язык интерфейса

Sidebar → **Язык** → Русский / English. Сохраняется в localStorage.

### 3.3. North Star сценарии

Готовые workflow в sidebar:

- Локальная фича end-to-end
- Agent autopilot с checkpoint
- Online research + patch
- Командный shared run
- Quality gate перед релизом

Кнопка **«Запустить агентом»** передаёт сценарий AI-агенту Termit.

### 3.4. Авто-запуск агента

Включите **«Авто-запуск агента»** — сценарии и задачи сразу создают agent run без ручного Send.

---

## 4. Работа с агентами

1. Вкладка **Agents** → выберите профиль агента.
2. Введите задачу или используйте North Star / Atomic workflow.
3. Следите за timeline (SSE): tool calls, verify, checkpoint.
4. При `confirm` — подтвердите risky tools в UI.
5. **Resume** — продолжение после failed run.

Policy preset задаёт: max tool steps, verify после patch, online/local режим.

---

## 5. API и автоматизация

Основные endpoint:

- `GET /health`, `GET /healthz`
- `POST /api/chat`, `POST /api/chat/stream`
- `POST /api/agents/{id}/runs`
- `GET /api/agents/runs/{id}/stream` (SSE)
- `POST /api/tools/apply_patch`
- `GET /api/metrics/executive-summary`

Полная автоматизация macOS:

```bash
./scripts/do_all_automatic.sh
```

---

## 6. Устранение неполадок

| Симптом | Решение |
|---------|---------|
| API offline | `./scripts/restart_server.sh` или LaunchAgent |
| Белый экран desktop | Пересоберите `.app`, `xattr -cr Termit.app` |
| Ollama down | `ollama serve`, проверьте модели |
| apply_patch blocked | Путь в `.env` sensitive list, нужен confirm |
| Agent не стартует | Создайте agent в `data/agents.json` |

Логи сервера: `.tools/termit-launchd.log`  
Логи desktop: кнопка **Логи** в sidebar.

---

## 7. Ссылки

- Репозиторий: README.md, START_HERE_RU.md
- Desktop: DESKTOP_QUICKSTART.md
- Программа обучения: TERMIT_TRAINING_RU.pdf (вкладка Справка)

Документ доступен локально в приложении Termit без интернета.
