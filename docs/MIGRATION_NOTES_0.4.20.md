# Migration Notes 0.4.20

## Scope

Task runner model override for coding eval A/B and agent runs.

Previous stable: `v0.4.19`.

## API

- `POST /api/tasks` — optional `model` forces runtime model for agent-backed auto tasks
- `POST /api/agents/{id}/runs` — optional `model` overrides profile/router selection
- Eval: `runner=task` with `model=` uses model-aware coding path (MT1–MT2)

## Model benchmark suite

Extended `data/eval_scenarios_model_benchmark.json`: MB1–MB3 (model_llm) + MT1–MT2 (task).

## Storage

SQLite task store adds `model` column on first write (auto-migrate).

## Operator checks

1. `./scripts/benchmark_baselines.py --scenarios model`
2. Confirm MT1/MT2 rows differ between termit and reference models
