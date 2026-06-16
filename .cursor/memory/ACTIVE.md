# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-16

## Сводка

- **Post-parity roadmap (0.3.6)** — полностью закрыт.
- **Следующий этап 0.3.7** — finetune loop closure: `training_loop_full.sh`, `docs/FINETUNE_LOOP_RU.md`.

## Файлы сессии

- `scripts/training_loop_full.sh`
- `docs/FINETUNE_LOOP_RU.md`
- `PROJECT_TASK_PROMPT_RU.md` — секция 0.3.7
- `OBSERVABILITY_CHECKLIST.md`, `DESKTOP_UX_TASK_PROMPT_RU.md` — актуализированы
- `.cursor/skills/termit-agent/SKILL.md` — новый вектор

## Открытые задачи

- [ ] +5% eval pass после stage1 cycle (GPU/train + baseline refresh)
- [ ] Weekly cron: `training_loop_full.sh` + auto baseline update on green gate
- [ ] Provider/cost observability dashboards
