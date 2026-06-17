# Migration Notes 0.4.19

## Scope

Model-aware eval runner for real A/B benchmark scoring between Termit runtime and reference models.

Previous stable: `v0.4.18`.

## New eval runner

- `model_llm` — calls LLM with explicit `model` parameter, validates `expect_contains`
- Scenarios MB1–MB3 in `data/eval_scenarios_model_benchmark.json` (not part of release gate suite)

## API

- `POST /api/eval/run` — optional `model` for model benchmark scenarios
- `POST /api/eval/benchmark/baselines` — defaults to MB1–MB3 when `use_model_benchmarks=true`

## CLI

```bash
./scripts/benchmark_baselines.py --scenarios model
./scripts/benchmark_baselines.py --scenarios model --no-persist
```

## Config

- `TERMIT_EVAL_MODEL_BENCHMARK_SCENARIOS_PATH=./data/eval_scenarios_model_benchmark.json`

## Operator checks

1. Ensure Ollama/cloud models are available for both termit and reference
2. Run model benchmark: `./scripts/benchmark_baselines.py --scenarios model`
3. Optional sync routing: `./scripts/sync_routing_benchmarks.py`
