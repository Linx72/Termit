# Migration Notes 0.4.18

## Scope

Auto-update `data/routing_benchmarks.json` from eval baseline comparison reports.

Previous stable: `v0.4.17`.

## API

- `POST /api/eval/benchmark/sync-routing` — operator role; sync from latest JSONL benchmark or inline `benchmark_report`
- `POST /api/eval/benchmark/baselines` — optional `sync_routing: true` + `blend_alpha` (default 0.3)

## CLI

```bash
./scripts/sync_routing_benchmarks.py --dry-run
./scripts/sync_routing_benchmarks.py --blend-alpha 0.3
```

## Routing policy

- Eval category → task type: `coding`/`cursor_parity` → `coding`, `local`/`retrieval` → `debug`, others → `general`
- Scores blended with existing values via EMA (`blend_alpha`, default 0.3)

## Operator checks

1. Run baseline compare: `POST /api/eval/benchmark/baselines` or `./scripts/benchmark_baselines.py`
2. Sync: `./scripts/sync_routing_benchmarks.py --dry-run` then without `--dry-run`
3. Verify: `GET /api/routing/benchmarks?task_type=coding`
