# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-20 — **v0.4.23 released** + prod handoff

## Сводка
- Release: https://github.com/Linx72/Termit/releases/tag/v0.4.23
- `prod_handoff_after_release.sh` — secrets/workflows checklist
- CI + beta-prod-gate (skip без URL) — success

## Real prod (нужны секреты пользователя)
- [ ] `OPENAI_COMPAT_API_KEY` в GitHub + `.env`
- [ ] `TERMIT_BETA_PROD_URL` + 5+ real desktop users
- [ ] GPU: `TERMIT_REMOTE_GPU_SSH` или NVIDIA → `gpu-dpo-learning-loop.yml`
