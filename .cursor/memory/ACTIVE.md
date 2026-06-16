# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-16

## Сводка

**0.4.4** — Product KPI targets (Phase 5).

### North Star KPI gates
- `task_success_rate_min` 75%, `automation_rate_min` 60%, `chat_p95_ttft_ms_max` 3000
- `DesktopKpiGateService` + telemetry metrics provider
- Prometheus: `termit_automation_rate`, `termit_desktop_kpi_gates_passed`, task counters
- Alerts: `TermitDesktopKpiGatesFailing`, `TermitLowTaskSuccessRate`
- `KpiGatePanel` — формат ms/s для latency gates

## Открытые задачи

- Мастер-план закрыт через 0.4.4; следующий «do all» — growth/KPI measurement или новый product track
