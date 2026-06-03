# Termit — онлайн-проекты и задания

Как использовать Termit для задач «по всему интернету»: исследование, сбор материалов, реализация и отчёт.

## Быстрый старт

```bash
cd ~/Projects/Termit
./scripts/setup_online_stack.sh          # SearXNG на :8888
TERMIT_INSTALL_PLAYWRIGHT=1 ./scripts/setup_online_stack.sh   # опционально: браузер Playwright
./scripts/restart_server.sh
```

## 1. Создать проект-задание

```bash
curl -s -X POST http://127.0.0.1:8765/api/assignments \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Landing page research",
    "brief": "Найди 3 референса лендингов SaaS, опиши структуру, сохрани черновик в deliverables/",
    "success_criteria": ["3 URL с citations", "outline.md в deliverables"],
    "target_urls": []
  }'
```

Папка: `data/assignments/<id>/` — `brief.md`, `deliverables/`, `journal/log.md`.

## 2. Агент для интернета

В UI или API создайте агента из шаблона **`online-project-manager`**:

- **allow_online** = true  
- **enabled_tools**: `web_search`, `web_automation`, `browser_*`, `read_file`, `apply_patch`, …

Или шаблоны **`research-fast`** / **`research-deep`** для только research.

## 3. Запуск

**Задача (task):**

```bash
curl -s -X POST http://127.0.0.1:8765/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "input": "Собери конкурентов для Termit и положи отчёт в deliverables",
    "task_type": "online_project",
    "mode": "auto"
  }'
```

**Агент (run):**

```bash
# POST /api/agents/{id}/runs
# payload: online_url, online_objective, input
```

## 4. Поиск в интернете

| Режим | `.env` |
|--------|--------|
| SearXNG (локально, без ключа) | `TERMIT_SEARCH_PROVIDER=searxng`, URL `:8888` |
| Exa | `TERMIT_SEARCH_PROVIDER=exa`, `TERMIT_SEARCH_API_KEY=...` |
| Perplexity | `TERMIT_SEARCH_PROVIDER=perplexity` |

## 5. Браузер (JS-сайты)

```bash
TERMIT_INSTALL_PLAYWRIGHT=1 ./scripts/setup_online_stack.sh
# TERMIT_BROWSER_BACKEND=playwright
```

Инструменты агента: `browser_navigate`, `browser_snapshot`, `browser_click` (click требует `confirmed=true`).

## 6. Доступ извне (опционально)

См. `HOSTED_DEPLOYMENT.md`, `docker-compose.yml` (Caddy). Включите `TERMIT_AUTH_ENABLED=true` перед публикацией API.

## Ограничения

- Логин, CAPTCHA, paywall — агент останавливается и просит вас (см. `TOOL_SAFETY_POLICY.md`).
- `browser_click` и опасные shell-команды — только с подтверждением.
- Полный «любой сайт под ключ» требует стабильной сети и при необходимости облачного воркера.
