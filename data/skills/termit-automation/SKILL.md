---
name: termit-automation
description: >-
  Termit do_all_automatic setup, server automation toggles (Stage1, daily
  improvement, crontab, agent schedules), and Desktop AutomationPanel via
  /api/ops/automation. Use when the user says do all automatic, automation
  toggles, disable schedulers, TERMIT_STAGE1, weekly eval cron, or server
  automation in Termit Desktop.
---

# Termit Automation

## When to apply

- «do all automatic», «автоматизация», «отключить scheduler/cron»
- Правки `AutomationPanel`, `automation_control_service`, `do_all_automatic.sh`
- Вопросы про флаги `.env` из automatic mode
- PATCH/GET `/api/ops/automation`

**Общий контекст Termit:** [`termit-agent`](../termit-agent/SKILL.md). **Мастер-промпт:** [`AUTOMATION_TASK_PROMPT_RU.md`](../../../AUTOMATION_TASK_PROMPT_RU.md).

## Quick commands

```bash
# Полный automatic setup (может менять .env + crontab)
TERMIT_SKIP_OLLAMA_CHECK=1 ./scripts/do_all_automatic.sh

# Только верификация (do all)
source .venv/bin/activate
python3 -m unittest discover -s tests -q
./scripts/smoke_http.sh

# Eval gate (правильно — через API)
curl -sf -X POST http://127.0.0.1:8765/api/eval/run-suite \
  -H 'Content-Type: application/json' \
  -d '{"limit":10,"persist_report":false}' \
  | python3 scripts/eval_ci_gate.py
```

## do all vs do all automatic

| Команда | Меняет .env/cron | Действие |
|---------|------------------|----------|
| do all | Нет | Тесты + smoke + сборки + eval sample |
| do all automatic | Да | `scripts/do_all_automatic.sh` + smoke + scheduler status |

## Отключение в продукте

1. **Desktop:** sidebar → «Автоматизация сервера» / «Server automation»
2. **API:** `GET/PATCH /api/ops/automation` — см. [reference.md](reference.md)
3. Master: `{ "automatic_mode_enabled": false }` выключает все toggles + cron markers

Runtime: встроенные scheduler'ы получают `set_enabled()` без перезапуска API; **исключение** — `auto_start_ollama` (нужен `restart_server.sh`).

## File map

| Что | Где |
|-----|-----|
| Setup script | `scripts/do_all_automatic.sh` |
| Control service | `app/services/automation_control_service.py` |
| Env writer | `app/services/env_file_service.py` |
| Routes | `app/api/routes/ops.py` |
| Scheduler hooks | `stage1_scheduler_service.py`, `daily_improvement_scheduler_service.py`, `agent_maintenance_scheduler_service.py`, `agent_schedule_service.py` |
| Desktop | `clients/termit-desktop/src/AutomationPanel.tsx` |
| Client SDK | `clients/termit-client/src/opsAutomation.ts` |
| Tests | `tests/test_automation_prefs.py` |

## After code changes

1. `python3 -m unittest tests.test_automation_prefs -q`
2. `discover -s tests` при широких правках
3. `./scripts/restart_server.sh` если backend
4. `./scripts/smoke_http.sh` — должен быть **200** на `/api/ops/automation`
5. Ответ пользователю на **русском** с фактическими passed/failed

## Anti-patterns

- `python3 scripts/eval_ci_gate.py --limit 10` без pipe (зависнет на stdin)
- Просить пользователя править `.env` вместо API/Desktop
- Считать automatic включённым без проверки `GET /api/ops/automation`

Подробности toggles и env keys: [reference.md](reference.md).
