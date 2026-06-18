# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-18

## Сводка
- Фаза 5 продолжена: `GET /api/ops/plan-status`, `PlanStatusService`, fix `cohort_size_d30`.
- `do_all_automatic`: opt-in `TERMIT_DO_ALL_PLAN=true`.
- PROJECT_TASK_PROMPT_RU.md: этап 0.4.21.

## Файлы сессии
- [`app/services/plan_status_service.py`](file:///Users/amoros/Projects/Termit/app/services/plan_status_service.py)
- [`app/api/routes/ops.py`](file:///Users/amoros/Projects/Termit/app/api/routes/ops.py)
- [`scripts/plan_status_check.py`](file:///Users/amoros/Projects/Termit/scripts/plan_status_check.py)

## Открытые задачи (фаза 5 — measurement)
- [ ] OPENAI_COMPAT_API_KEY для cloud benchmark
- [ ] DPO real train на GPU
- [ ] Product KPI gates — beta cohort ≥5 в prod
