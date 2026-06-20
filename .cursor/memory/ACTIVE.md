# Session memory (AutoCheckPoint)

**Последнее обновление:** 2026-06-20 (ось B harness)

## Сводка
- **Ось A:** vLLM provider (`vllm:` prefix), docker-compose.vllm.yml, phase B ladder scripts.
- **Ось B (полная):** lazy tools, cohesion partition, describe_tools API.
- Док: `docs/MODEL_LADDER_RU.md` — фаза A (Ollama) + фаза B (vLLM hybrid).

## Открытые задачи
- [ ] Real GPU DPO + cloud key (0.4.23)
- [ ] Prod beta D30 ≥35% без dev seed
- [x] pre_release_check + release-gate-staging CI + do_all_automatic staging opt-in
