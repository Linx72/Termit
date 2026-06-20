# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-20 — **SDXL ComfyUI E2E green**

## Сводка
- **SDXL E2E:** ComfyUI :8188 + checkpoint 6.5 GB + `generate_image provider=comfy` → PNG OK (~25s @512²)
- Commit `61e1531`: media_provider_comfy, scripts, Desktop, MS12 eval
- **do_all_automatic** — exit 0; v0.4.27 Release green

## Открытые задачи
- [ ] `OPENAI_COMPAT_API_KEY` в `.env` + GitHub Secrets
- [ ] GPU / `TERMIT_REMOTE_GPU_SSH` → real DPO
- [ ] `TERMIT_BETA_PROD_URL` + real desktop users
