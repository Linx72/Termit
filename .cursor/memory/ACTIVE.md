# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-20 — **v0.4.27 released, CI green**

## Сводка
- **v0.4.27** — Release success, desktop zip на GitHub
- CI + Agent Eval — **success** (fast gate)
- Docs: `MIGRATION_NOTES_0.4.27.md`, `ROLLBACK_PLAN_0.4.27.md`
- Release Gate Staging: Colima fail на macOS runner → workflow на `ubuntu-latest`

## Real prod (нужны секреты пользователя)
- [ ] `OPENAI_COMPAT_API_KEY` → GitHub Secrets + `.env`
- [ ] `TERMIT_BETA_PROD_URL` + 5+ real desktop users
- [ ] GPU / `TERMIT_REMOTE_GPU_SSH` → real DPO
