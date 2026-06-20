# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-20 — **v0.4.27 полностью green**

## Сводка
- **v0.4.27** — Release + desktop zip: https://github.com/Linx72/Termit/releases/tag/v0.4.27
- CI + Agent Eval — **success**
- **Release Gate Staging** — **success** (ubuntu Docker, operator-key, non-strict beta)
- Docs: `MIGRATION_NOTES_0.4.27.md`, `ROLLBACK_PLAN_0.4.27.md`

## Real prod (нужны секреты пользователя)
- [ ] `OPENAI_COMPAT_API_KEY` → GitHub Secrets + `.env` → cloud benchmark vs V4
- [ ] `TERMIT_BETA_PROD_URL` + 5+ real desktop users
- [ ] GPU / `TERMIT_REMOTE_GPU_SSH` → real DPO + KPI +5%
