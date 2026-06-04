# Termit — промпт: автоматизация и desktop (do_all_automatic)

> **Назначение:** мастер-промпт для агентов при запросах «do all automatic», «автоматизация», «отключить scheduler», «desktop automation», настройка фоновых задач Termit.
>
> **Skill:** [`.cursor/skills/termit-automation/SKILL.md`](file:///Users/amoros/Projects/Termit/.cursor/skills/termit-automation/SKILL.md)
>
> **Связанные документы:** [`PROJECT_TASK_PROMPT_RU.md`](PROJECT_TASK_PROMPT_RU.md), [`docs/DESKTOP_NORTH_STAR_RU.md`](docs/DESKTOP_NORTH_STAR_RU.md), [`START_HERE_RU.md`](START_HERE_RU.md)

---

## Северная звезда

Пользователь один раз включает **авто-режим** (`do_all_automatic`) — Termit сам держит API, гоняет eval/finetune/improvement по расписанию. В любой момент можно **выключить всё или по частям** в Termit Desktop без ручного редактирования `.env`.

---

## Два режима запроса

| Запрос пользователя | Действие агента |
|---------------------|-----------------|
| **do all** | Верификация: unittest, smoke, сборки, eval gate (limit 10). Без изменения crontab/.env. |
| **do all automatic** | `./scripts/do_all_automatic.sh` (+ `TERMIT_SKIP_OLLAMA_CHECK=1` если Ollama долго). Затем smoke + статус scheduler. |

**Не путать:** `python3 scripts/eval_ci_gate.py` читает JSON **из stdin** — всегда подавать через `curl -X POST …/api/eval/run-suite | python3 scripts/eval_ci_gate.py`.

---

## Что включает do_all_automatic

1. `do_all_setup.sh` — venv, тесты, clients, LaunchAgent `com.termit.server`
2. Флаги в `.env`:
   - `TERMIT_STAGE1_SCHEDULE_ENABLED=true`
   - `TERMIT_DAILY_IMPROVEMENT_ENABLED=true`
   - `TERMIT_AGENT_SCHEDULES_ENABLED=true`
   - `TERMIT_AGENT_MAINTENANCE_ENABLED=true`
   - `TERMIT_RETRIEVAL_AUTO_REINDEX=true`
   - `TERMIT_FINETUNE_AUTO_CAPTURE_SIGNALS=true`
   - `TERMIT_AUTO_START_OLLAMA=true`
   - `TERMIT_EVAL_CI_LIMIT=53`
3. `restart_server.sh`
4. Crontab: weekly eval (пн 04:00), daily improvement (02:05)
5. `smoke_http.sh`

---

## Отключение в приложении (продукт)

**Desktop:** sidebar → **«Автоматизация сервера»** (`AutomationPanel`).

**API:**

```http
GET  /api/ops/automation
PATCH /api/ops/automation
```

Примеры тела PATCH:

```json
{ "automatic_mode_enabled": false }
```

```json
{ "toggles": { "stage1_schedule": false, "weekly_eval_cron": false } }
```

| toggle_id | Назначение |
|-----------|------------|
| `stage1_schedule` | Встроенный weekly Stage1 finetune |
| `daily_improvement` | Встроенный nightly improvement |
| `agent_schedules` | Cron agent runs (platform) |
| `agent_maintenance` | Cleanup runs + metrics snapshots |
| `retrieval_auto_reindex` | Фоновый reindex |
| `finetune_auto_capture` | Захват training signals |
| `auto_start_ollama` | Старт Ollama при boot API (**нужен restart**) |
| `weekly_eval_cron` | Crontab `scripts/weekly_eval.sh` |
| `daily_improvement_cron` | Crontab `scripts/daily_improvement.sh` |

Переключатели пишут в `.env` (`TERMIT_ENV_FILE` или `./.env`) и **сразу** stop/start встроенных scheduler threads. Crontab — через установку/удаление строк с маркерами `# termit-weekly-eval`, `# termit-daily-improvement`.

**RBAC:** PATCH требует `operator` (или `admin`), если `TERMIT_AUTH_ENABLED=true`.

---

## Ключевые файлы

| Область | Путь |
|---------|------|
| Скрипт setup | `scripts/do_all_automatic.sh` |
| API | `app/api/routes/ops.py` (`/automation`) |
| Сервис | `app/services/automation_control_service.py` |
| .env I/O | `app/services/env_file_service.py` |
| Desktop UI | `clients/termit-desktop/src/AutomationPanel.tsx` |
| SDK | `clients/termit-client/src/opsAutomation.ts` |
| Тесты | `tests/test_automation_prefs.py` |
| Smoke | `scripts/smoke_http.sh` (строка `/api/ops/automation`) |

---

## Чеклист агента после изменений

```
- [ ] python -m unittest tests.test_automation_prefs -q
- [ ] python -m unittest discover -s tests -q
- [ ] ./scripts/restart_server.sh (если менялся backend)
- [ ] ./scripts/smoke_http.sh
- [ ] clients: npm run build в termit-client + termit-desktop
- [ ] Итог: passed/failed, HTTP-коды (не «должно работать»)
```

Опционально eval:

```bash
curl -sf -X POST http://127.0.0.1:8765/api/eval/run-suite \
  -H 'Content-Type: application/json' \
  -d '{"limit":10,"persist_report":false}' \
  | python3 scripts/eval_ci_gate.py
```

---

## Desktop North Star (контекст)

Journeys + KPI: [`docs/DESKTOP_NORTH_STAR_RU.md`](docs/DESKTOP_NORTH_STAR_RU.md), telemetry: `POST /api/desktop/workflow-events`.

Автоматизация сервера **не заменяет** journey «agent_autopilot» — это фоновые pipeline; UX-автопилот настраивается отдельно (`autoExecuteWithAgent`, policy presets).

---

## Anti-patterns

- Запускать `eval_ci_gate.py` без stdin от `run-suite`
- Симулировать успех `do_all_automatic`, если скрипт не завершился
- Просить пользователя «отредактируйте .env» при наличии Desktop/API
- Коммитить без явной просьбы пользователя
