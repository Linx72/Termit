# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-20 — **SDXL ComfyUI local provider**

## Сводка
- **SDXL local:** `media_provider_comfy.py`, `scripts/setup_comfy_sdxl.sh`, provider `comfy`/`sdxl`, MS12 eval, Desktop option
- **do_all_automatic** (plan + learning + hosted) — exit 0 ~5.4 min
- v0.4.27 Release + CI + Release Gate Staging — green

## Открытые задачи
- [ ] `./scripts/setup_comfy_sdxl.sh` + `start_comfy_sidecar.sh` (weights ~6.5 GB)
- [ ] `OPENAI_COMPAT_API_KEY` в `.env` + GitHub Secrets
- [ ] GPU / `TERMIT_REMOTE_GPU_SSH` → real DPO
- [ ] `TERMIT_BETA_PROD_URL` + real desktop users
