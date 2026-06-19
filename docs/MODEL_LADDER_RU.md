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

```text
LOW coding        → ollama:qwen2.5-coder (7B, fast)
DEFAULT agents    → ollama:termit-core-ft (FROM qwen2.5-coder:14b)
CODE fallback     → ollama:qwen2.5-coder:14b
HIGH / dual-pass  → openai_compat:Qwen2.5-Coder-32B (нужен API key)
Frontier          → openai_compat:DeepSeek-V3
Embeddings        → nomic-embed-text
```

## Быстрый апгрейд (фаза A)

```bash
./scripts/upgrade_model_ladder_phase_a.sh
./scripts/restart_server.sh
```

Создаёт `termit-core-ft` из [`data/finetune/recipes/termit-core-ft.Modelfile`](file:///Users/amoros/Projects/Termit/data/finetune/recipes/termit-core-ft.Modelfile), warm Ollama.

## Dual-pass

`TERMIT_DUAL_PASS_ENABLED=true` — draft local → validator (`analysis` chain). С cloud key validator идёт в 32B; без ключа — локальный analysis model.

## Сравнение с внешними моделями

| Модель | Coding + tools | Online | Local |
|--------|----------------|--------|-------|
| GPT-4.1 / o4-mini | ★★★★★ | API | Cloud |
| Claude Sonnet | ★★★★★ | API | Cloud |
| DeepSeek-V3 | ★★★★☆ | API | Cloud |
| Qwen2.5-Coder 14B | ★★★★☆ | Слабый | Ollama |
| termit-core-ft 14B | ★★★☆☆ → ★★★★ после DPO | Harness | Ollama |

Moat Termit — **harness** (tools, eval, finetune), не одна weights file.

## Дальше (фазы B–E)

См. план в чате / `PROJECT_TASK_PROMPT_RU.md` 0.4.23–0.4.25: GPU DPO, beta cohort, symbol graph, search providers.
