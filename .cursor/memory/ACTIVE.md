# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-20 — **v0.4.27 Release CI fix (DPO + venv)**

## Сводка
- v0.4.25 release без assets (Release workflow: DPO contract JSON parse)
- v0.4.26: fix DPO export parse, agent-eval deep limit 53, staging docker install
- Prod Readiness workflow — success; Release Gate Staging — docker missing (fixed in 0.4.26)

## Real prod (нужны секреты пользователя)
- [ ] `OPENAI_COMPAT_API_KEY` → GitHub Secrets + `.env`
- [ ] `TERMIT_BETA_PROD_URL` + 5+ real desktop users
- [ ] GPU / `TERMIT_REMOTE_GPU_SSH` → real DPO
