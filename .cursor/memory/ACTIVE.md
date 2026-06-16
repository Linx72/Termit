# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-16

## Сводка

- **Track 3 (Desktop UX)** — RuntimeStatusBar, Quick Start wizard, HealthDashboard activeRuns/by_outcome_class, repo→workspace auto-fill.
- **Track 2–4** — merged в main (PR #11): outcome classes, eval regression, policy fallback, CI orch gates.
- **Track 4** — 74 eval-сценария в `data/eval_scenarios.json` (≥40+ DoD закрыт).

## Файлы сессии (Track 3)

- `clients/termit-desktop/src/RuntimeStatusBar.tsx` (новый)
- `clients/termit-desktop/src/App.tsx`, `FirstRunWizard.tsx`, `HealthDashboard.tsx`
- `clients/termit-desktop/src/i18n.ts`, `index.css`
- `clients/termit-client/src/types.ts` — `by_outcome_class`

## Открытые задачи

- [x] Push Track 3 на main + CI green (run 27639779818)
- [x] Track 5: `docs/RELEASE_FLOW.md`, `scripts/release_pack.sh`
- [ ] Track 1: e2e flake tail (unstable → nightly only; PR deterministic)
- [ ] Track 5: SLO/SLA dashboards и алерты
- [ ] Фаза 5: docker prod polish, backup SQLite UI
