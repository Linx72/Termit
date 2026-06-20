# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-20 — **do_all_automatic green + commit pending**

## Сводка
- **do_all_automatic** (plan + learning + hosted) — exit 0 ~5.4 min
- Fix: `do_all_automatic.sh` без `source .env`; `.env.example` кавычки VERIFY_CMD
- Cloud benchmark: `OPENAI_COMPAT_API_KEY` в `.env` **пустой** — probe missing_api_key
- v0.4.27 Release + CI + Release Gate Staging — green

## Real prod blockers
- [ ] Заполнить `OPENAI_COMPAT_API_KEY` в `.env` + GitHub Secrets
- [ ] GPU / `TERMIT_REMOTE_GPU_SSH` → real DPO
- [ ] `TERMIT_BETA_PROD_URL` + real desktop users
