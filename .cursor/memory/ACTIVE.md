# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-16

## Сводка

- **0.3.6 stable** — tagged, GitHub release, CI green.
- **Фаза 5 закрыта** — signed desktop: `package_desktop.sh` → `TermitShell.app`, release workflow + checksums.
- Post-parity roadmap (Track 1–5, Фаза 5) — **complete**.

## Ключевые файлы (signed desktop)

- `scripts/package_desktop.sh` — wrapper для shell bundle
- `scripts/package_termit_shell.sh` — codesign + notary
- `scripts/verify_desktop_signature.sh`
- `docs/DESKTOP_SIGNING_RU.md`
- `.github/workflows/release.yml`

## Открытые задачи

- (none) — следующий этап: новые фичи по запросу или MS8/MS9 infra
