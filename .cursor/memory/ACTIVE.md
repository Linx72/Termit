# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-17T22:59:01Z

**Причина:** session stop

**Последний checkpoint:** [`20260617-225901_c9653b0d-c553-4202-b36f-.md`](checkpoints/20260617-225901_c9653b0d-c553-4202-b36f-.md)

## Сводка
- ## Автоматический режим включён `TERMIT_SKIP_OLLAMA_CHECK=1 ./scripts/do_all_automatic.sh` — **exit 0**. ### Что сделано **1. Automation API** ([`automation_control_service.py`](file:///Users/amoros/Projects/Termit/app/services/automation_control_service.py)) - Weekly cron → `we…
- # Termit: стадия проекта и глубокий план развития ## Где вы сейчас **Версия:** `0.4.20` (июнь 2026). **Стадия:** post-parity → **production-hardening + learning loop**. Это не «MVP агента», а уже **локальная agent-платформа** с harness, клиентами, eval/finetune и автоматизацией.…
- ## Итог `do all` Закрыты пункты из горизонта A: **telemetry fallback**, **полный crontab**, **verify**. ### 1. Метрики tool-loop fallback В оркестраторе и Prometheus: - `orchestration_tool_loop_fallback_total` — сколько раз сработал fallback `list_files` - `orchestration_tool_lo…
- ## Итог `do all` Закрыт блок **strict live orchestration tier** и добавлен захват KPI baseline. ### Strict live gate - Tier `strict_live` в [`eval_orchestration_gate_tiers.py`](file:///Users/amoros/Projects/Termit/app/services/eval_orchestration_gate_tiers.py): `pass_rate=1.0`,…
- ## Итог `do all` Закрыт блок **KPI learning loop** и доведён **full verify** до зелёного. ### Что сделано **1. KPI baseline → training loop** - [`weekly_full_cycle.sh`](file:///Users/amoros/Projects/Termit/scripts/weekly_full_cycle.sh) — шаг 0: `capture_eval_kpi_baseline.sh` пер…
- ## Продолжение — итог Закрыты два блокера и прогнан полный weekly cycle. ### Исправления **1. Capability gate в weekly loop** `weekly_eval.sh` и `weekly_closed_loop.sh` используют tier **`ci`** (не `release`). Release остаётся для `quarterly_capability.sh`. Раньше цикл падал на…

## Файлы сессии
- `/Users/amoros/Projects/Termit/CHANGELOG.md`
- `/Users/amoros/Projects/Termit/scripts/finetune_eval_kpi_gate.py`
- `/Users/amoros/Projects/Termit/app/domain/schemas.py`
- `/Users/amoros/Projects/Termit/app/api/routes/metrics.py`
- `/Users/amoros/Projects/Termit/scripts/install_automation_crontabs.sh`
- `/Users/amoros/Projects/Termit/tests/test_response_cache_and_metrics.py`
- `/Users/amoros/Projects/Termit/app/services/eval_orchestration_gate_tiers.py`
- `/Users/amoros/Projects/Termit/app/api/routes/orchestration.py`
- `/Users/amoros/Projects/Termit/scripts/eval_orchestration_spike.py`
- `/Users/amoros/Projects/Termit/scripts/run_strict_live_orchestration_gate.sh`
- `/Users/amoros/Projects/Termit/scripts/capture_eval_kpi_baseline.sh`
- `/Users/amoros/Projects/Termit/tests/test_orchestration_api.py`
- `/Users/amoros/Projects/Termit/tests/test_eval_orchestration_gate_tiers.py`
- `/Users/amoros/Projects/Termit/tests`
- `/Users/amoros/Projects/Termit/scripts/training_loop_weekly.sh`
- `/Users/amoros/Projects/Termit/scripts/training_loop_full.sh`
- `/Users/amoros/Projects/Termit/scripts/weekly_full_cycle.sh`
- `/Users/amoros/Projects/Termit/data/eval_kpi_baseline.json`
- `/Users/amoros/Projects/Termit/app`
- `/tmp/weekly_full_cycle.log`
- `/Users/amoros/Projects/Termit/scripts/weekly_eval.sh`
- `/Users/amoros/Projects/Termit/scripts/weekly_closed_loop.sh`
- `/Users/amoros/Projects/Termit/tests/test_finetune_training_dashboard.py`
- `/tmp/weekly_full_cycle2.log`
- `/Users/amoros/Projects/Termit/data/eval_kpi_last.json`

## Открытые задачи
- [ ] Заполните вручную или через compact-chat после крупной сессии
