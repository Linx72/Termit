# Migration Notes 0.4.25

## Scope

DeepSeek V4 ladder, eval 3.0 (TB1–TB3, SWE in model_bound), `v4_ladder_smoke`

Previous stable: `v0.4.24`.

## Configuration changes

Review `.env` / `.env.example` since `v0.4.24`:

| Key | Default (new) | Notes |
|-----|---------------|-------|
| `TERMIT_FRONTIER_FALLBACK_MODEL` | `openai_compat:deepseek-ai/DeepSeek-V4-Pro` | was often `DeepSeek-V3` |
| `TERMIT_CLOUD_TEACHER_MODEL` | V4-Pro | finetune / judge fallback |
| `TERMIT_EVAL_BENCHMARK_REFERENCE_MODEL` | V4-Pro | capability benchmark |
| `TERMIT_FRONTIER_FALLBACK_CHAIN` | V4-Pro, V4-Flash, V3 | optional explicit chain |
| `TERMIT_EVAL_TERMINAL_SCENARIOS_PATH` | `./data/eval_scenarios_terminal.json` | TB1–TB3 |
| `TERMIT_ROUTING_MAX_CANDIDATES` | `6` | was `4`; needed for full frontier chain |

If your OpenAI-compat provider does not expose V4 yet, temporarily set:

```bash
TERMIT_EVAL_BENCHMARK_REFERENCE_MODEL=openai_compat:deepseek-ai/DeepSeek-V3
TERMIT_FRONTIER_FALLBACK_MODEL=openai_compat:deepseek-ai/DeepSeek-V3
```

No SQLite schema migrations in this release.

## CI / release process

- Fast gate (PR/main): `.github/workflows/ci.yml` (+ `v4_ladder_smoke.sh` on main)
- Deep gate (nightly): full eval suite in CI
- Release gate (local/manual): `TERMIT_EVAL_GATE_TIER=release ./scripts/release_smoke_extended.sh`
- Deterministic core: `./scripts/release_smoke_core.sh`
- V4 ladder smoke (no cloud key): `./scripts/v4_ladder_smoke.sh`

## Operator checks after upgrade

1. `./scripts/v4_ladder_smoke.sh`
2. `./scripts/release_smoke_core.sh`
3. `GET /health`, `GET /healthz`, `GET /api/ops/readiness` => 200
4. Desktop (if used): `cd clients/termit-desktop && npm run build`
5. With `OPENAI_COMPAT_API_KEY`: `TERMIT_CAP_REFRESH_BASELINE=1 ./scripts/cloud_benchmark_cycle.sh`

## Prod handoff (secrets)

See `./scripts/prod_handoff_after_release.sh` — GitHub Secrets: `OPENAI_COMPAT_API_KEY`, `TERMIT_BETA_PROD_URL`.
