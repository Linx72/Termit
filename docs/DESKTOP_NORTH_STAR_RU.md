# Termit Desktop — North Star (local + online)

Документ фиксирует 5 ключевых user journeys и KPI для сравнения с Cursor-классом UX.

Источник данных для API/desktop: [`data/desktop_north_star.json`](../data/desktop_north_star.json).

## Journeys

| ID | Сценарий | Режим | Основной tab |
|----|----------|-------|--------------|
| `local_feature` | Plan → Composer → apply → verify → commit | local | plan |
| `agent_autopilot` | Agent run + checkpoint + resume | local/hybrid | agents |
| `online_research` | @web → composer → safe apply + rollback | online/hybrid | composer |
| `team_shared_run` | Share run + team policy | online/hybrid | online |
| `quality_gate` | KPI gate + heavy eval job | local/online | online |

## KPI targets

| Метрика | Target | Где меряем |
|---------|--------|------------|
| TTFUC (time to first useful change) | < 90 сек | desktop workflow telemetry |
| Patch acceptance rate | > 70% | patch outcomes / composer apply |
| Verify pass rate | > 85% | agent verify events |
| Agent resume median | < 30 сек | run resume latency |
| Local-only task share | > 60% | execution_mode=local runs |
| Eval pass rate | > 75% | `/api/eval/dashboard` |
| Tool loop completion | > 80% | `/api/ops/agent-runs/metrics` |

## API

- `GET /api/desktop/journeys` — journeys + KPI targets
- `GET /api/desktop/kpi-gates` — статус gate по KPI
- `GET /api/desktop/policy-presets` — solo / team / strict
- `GET|POST /api/desktop/shared-runs` — командная доска run'ов
- `GET|POST /api/desktop/heavy-jobs` — фоновые eval/orchestration jobs

## Policy presets

Файл: [`data/desktop_policy_presets.json`](../data/desktop_policy_presets.json).

Передаётся в agent run как `policy_preset` в `POST /api/agents/{id}/runs`.
