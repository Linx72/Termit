# Model ladder Termit (фаза A–E)

Как Termit выбирает модели и как улучшить coding / online / задачи пользователя.

## Роли (runtime)

| Env | Назначение |
|-----|------------|
| `TERMIT_CODE_MODEL` | Агенты, tool loop, coding |
| `TERMIT_FAST_MODEL` | Простые запросы, tab completion |
| `TERMIT_CODE_FALLBACK_MODEL` | Retry при ошибке провайдера |
| `TERMIT_ANALYSIS_FALLBACK_MODEL` | Review/debug validator (dual-pass) |
| `TERMIT_FRONTIER_FALLBACK_MODEL` | High complexity coding |
| `TERMIT_TEACHER_*` | **Только** finetune/benchmark, не chat |

Роутинг: [`app/services/model_router.py`](file:///Users/amoros/Projects/Termit/app/services/model_router.py) — task_type + complexity + cost-aware.

## Рекомендуемая ladder (2026)

### Фаза B — vLLM + hybrid (production GPU)

```text
LOW / tab         → ollama:qwen2.5-coder (7B, быстрый FIM)
CODE agents       → vllm:Qwen/Qwen3-Coder-Next (MoE, native tools)
CODE fallback     → ollama:termit-core-ft или qwen2.5-coder:14b
HIGH / dual-pass  → openai_compat:DeepSeek-V3 (cloud key)
Embeddings        → nomic-embed-text (Ollama)
```

### Фаза A — Ollama only (dev / без GPU)

```text
LOW coding        → ollama:qwen2.5-coder (7B, fast)
DEFAULT agents    → ollama:termit-core-ft (FROM qwen2.5-coder:14b)
CODE fallback     → ollama:qwen2.5-coder:14b
HIGH / dual-pass  → openai_compat:Qwen2.5-Coder-32B (нужен API key)
Frontier          → openai_compat:DeepSeek-V3
Embeddings        → nomic-embed-text
```

## Быстрый апгрейд

### Фаза B (vLLM, рекомендуется при NVIDIA GPU)

```bash
./scripts/upgrade_model_ladder_phase_b.sh
# или вручную:
./scripts/start_vllm_sidecar.sh
./scripts/check_vllm_models.sh
./scripts/restart_server.sh
```

Docker prod:

```bash
docker compose -f docker-compose.yml -f docker-compose.vllm.yml --profile vllm up -d
```

Env:

```bash
TERMIT_VLLM_ENABLED=true
TERMIT_VLLM_BASE_URL=http://127.0.0.1:8000
TERMIT_CODE_MODEL=vllm:Qwen/Qwen3-Coder-Next
TERMIT_FAST_MODEL=ollama:qwen2.5-coder
```

Провайдер: [`app/services/providers/vllm_provider.py`](file:///Users/amoros/Projects/Termit/app/services/providers/vllm_provider.py) — OpenAI `/v1/chat/completions` + native tool calling.

### Фаза A (Ollama)

```bash
./scripts/upgrade_model_ladder_phase_a.sh
./scripts/restart_server.sh
```

Создаёт `termit-core-ft` из [`data/finetune/recipes/termit-core-ft.Modelfile`](file:///Users/amoros/Projects/Termit/data/finetune/recipes/termit-core-ft.Modelfile), warm Ollama.

## Dual-pass

`TERMIT_DUAL_PASS_ENABLED=true` — draft local/vLLM → validator (`analysis` chain). С cloud key validator идёт в frontier; без ключа — локальный analysis model.

## Native tool calling

Agent tool loop для `ollama:*` и `vllm:*` использует OpenAI-style tools. При ошибке API — fallback на JSON action loop.

## Сравнение inference stack

| Stack | tok/s (оценка) | VRAM | Tool calling |
|-------|----------------|------|--------------|
| Ollama 14B dense | 1× | ~12 GB | ✓ qwen2.5 |
| vLLM Qwen3-Coder-Next MoE | 3–5× | ~24–48 GB | ✓ hermes parser |
| Cloud DeepSeek-V3 | quality↑ | — | ✓ |

Moat Termit — **harness** (tools, eval, finetune, ось B lazy context), не одна weights file.

## Связанные env (ось B harness)

```bash
TERMIT_LAZY_TOOL_SCHEMAS=true
TERMIT_AGENT_SKIP_STEP_ENRICHMENT=true
TERMIT_COHESION_PARTITION_ENABLED=true
```

## Дальше (фазы C–E)

GPU DPO train, cloud benchmark gate, beta product KPI — см. `PROJECT_TASK_PROMPT_RU.md` 0.4.23–0.4.25.
