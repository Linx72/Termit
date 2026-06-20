# Migration Notes 0.4.27

## Scope

Post-release CI fixes: DPO contract gate без `.venv`, Release workflow venv, agent-eval fast gate.

Previous stable with V4 ladder: `v0.4.25`. Recommended current: **`v0.4.27`** (desktop assets + green Release).

## Configuration changes

Нет новых env-ключей относительно `v0.4.25`. Ladder V4 — см. [MIGRATION_NOTES_0.4.25.md](./MIGRATION_NOTES_0.4.25.md).

## CI / release process

| Workflow | Изменение |
|----------|-----------|
| `Release` | `python -m venv .venv` перед unit tests и `package_desktop.sh` |
| `Agent Eval` | только fast gate (`cursor_parity`, limit 20) — как `ci.yml` push |
| `release-gate-staging.yml` | `brew install colima docker` на macOS runner |

Локально DPO contract устойчив без `.venv`: fallback на `data/finetune/datasets/sample_dpo_contract.jsonl`.

## Operator checks after upgrade

1. `./scripts/v4_ladder_smoke.sh`
2. `./scripts/release_smoke_core.sh`
3. `GET /health`, `GET /healthz`, `GET /api/ops/readiness` => 200
4. Desktop: скачать [v0.4.27 release](https://github.com/Linx72/Termit/releases/tag/v0.4.27) или `./scripts/package_desktop.sh`

## Prod handoff (secrets)

См. `./scripts/prod_handoff_after_release.sh`:

- `OPENAI_COMPAT_API_KEY` — cloud benchmark, learning loop judge
- `TERMIT_BETA_PROD_URL` — prod beta gate
- GPU / `TERMIT_REMOTE_GPU_SSH` — real DPO
