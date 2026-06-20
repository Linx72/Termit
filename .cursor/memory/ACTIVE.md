# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-20 — **v0.4.25 готов к коммиту**

## Сводка
- VERSION 0.4.25: V4 ladder, eval 3.0 (TB/SWE), eval_standalone, v4_ladder_smoke
- CI main: шаг `v4_ladder_smoke.sh`; START_HERE §6a обновлён
- `./scripts/v4_ladder_smoke.sh` — exit 0 (без cloud key)
- **Не сделано:** git commit/push/tag (скажите «закоммить» / «push» / «релиз»)

## Real prod (нужны секреты пользователя)
- [ ] `OPENAI_COMPAT_API_KEY` в GitHub + `.env`
- [ ] `TERMIT_BETA_PROD_URL` + 5+ real desktop users
- [ ] GPU: `TERMIT_REMOTE_GPU_SSH` или NVIDIA → real DPO + KPI +5%
