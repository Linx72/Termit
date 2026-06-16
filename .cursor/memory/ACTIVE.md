# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-16

## Сводка

- **0.3.6** — SLO/Grafana, DLQ UI, OpsSecurityPanel (quota + audit export), graceful shutdown, patch secret scan.
- **Фаза 5** — почти закрыта; осталось: signed desktop builds.

## Ключевые файлы

- `app/services/agent_service.py` — graceful stop + draining
- `clients/termit-desktop/src/OpsSecurityPanel.tsx`
- `app/services/guardrail_service.py` — patch secret scan
- `GET /api/ops/runtime-policy`

## Открытые задачи

- [ ] Tag `v0.3.6` + GitHub release
- [ ] Signed desktop builds
