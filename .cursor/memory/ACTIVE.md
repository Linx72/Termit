# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-19T07:20:00Z

## Сводка

- **Фаза A model ladder:** 14B base Modelfile, upgrade_model_ladder_phase_a.sh, docs/MODEL_LADDER_RU.md
- dual-pass default true в .env.example
- do all: hosted 8/8 OK, overall_ok=false (4–5 warnings)

## Открытые задачи

- [ ] `./scripts/upgrade_model_ladder_phase_a.sh` на машине с Ollama
- [ ] OPENAI_COMPAT_API_KEY
- [ ] GPU DPO, beta ≥5
