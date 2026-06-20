# Termit Release Checklist

## 1) Pre-release quality

- **Единый gate (рекомендуется):** `./scripts/pre_release_check.sh`
  - Local: `release_gate_local.sh` + plan dev green
  - Staging (auto если `:8080` up): `release_gate_staging.sh`
- **Prod readiness (plan + preflight + optional gates):** `./scripts/prod_readiness_check.sh`
- Run tests: `python -m unittest discover -s tests -q` (689+ tests)
- Verify API health: `GET /health`
- Verify providers status: `GET /api/providers/status`
- Verify session export formats:
  - `GET /api/sessions/{id}/export?format=markdown`
  - `GET /api/sessions/{id}/export?format=txt`
  - `GET /api/sessions/{id}/export?format=json`

## 2) Runtime and config

- If auth enabled, verify:
  - missing key -> `401`
  - invalid key -> `401`
  - quota exceeded -> `429`
  - `GET /api/usage` with valid key

- Confirm `.env` values:
  - `TERMIT_PORT`
  - `TERMIT_MEMORY_BACKEND`
  - `TERMIT_MEMORY_SQLITE_PATH`
  - model routing (`TERMIT_*_MODEL`, `TERMIT_*_FALLBACK_MODEL`)
- Ensure writable path for SQLite DB when `TERMIT_MEMORY_BACKEND=sqlite`
- Ensure provider endpoints are reachable from runtime host

## 3) UI checks

- `Run` request works and shows metadata
- `Run stream` shows `meta/token/error/done` handling correctly
- `Export session` shows exported content
- `Download export` saves correct extension (`.md`, `.txt`, `.json`)

## 4) Safety and operations

- Verify tooling path traversal protections (`/api/tools/read_file`, `/api/tools/list_files`)
- Review logs for unhandled exceptions during smoke tests
- Confirm `.db`, `.env`, and virtualenv are ignored by git

## 5) Release handoff

- Update `README.md` with any changed endpoints/config
- Tag release version in git (for example `v0.1.0`)
- Capture known limitations (provider availability, local runtime assumptions)
- Publish quick start commands for users
- Write migration notes for the release (example: `docs/MIGRATION_NOTES_0.3.5.md`)
- Write rollback plan with explicit smoke/health verification (example: `docs/ROLLBACK_PLAN_0.3.5.md`)

## 6) Cursor parity release gates

- Quality gate matrix (fast/deep/release):
  - Fast gate (PR/main CI): cursor parity slice `limit=20` in `.github/workflows/ci.yml` (`Eval fast gate (PR/main)`).
  - Deep gate (nightly): full eval suite `limit=53` in `.github/workflows/ci.yml` (`Nightly eval deep gate`).
  - Release gate (local/manual with cloud judge): `TERMIT_EVAL_GATE_TIER=release ./scripts/release_smoke_extended.sh`
  - Nightly extended smoke (CI): pass-rate gate only (`TERMIT_EVAL_MIN_PASS_RATE=0.95`) in `.github/workflows/ci.yml` (`Extended release smoke`); cloud judge coverage is not required on GitHub runners.

- Release smoke profiles:
  - Pre-release bundle: `./scripts/pre_release_check.sh`
  - Staging gate: `./scripts/release_gate_staging.sh` (CI: `.github/workflows/release-gate-staging.yml`)
  - Deterministic core (default): `./scripts/release_smoke_core.sh` (includes `confirm_run` regression tests)
  - Extended suite (nightly/integration): `./scripts/release_smoke_extended.sh`
  - Dedicated nightly workflow: `.github/workflows/nightly-extended-smoke.yml`
  - После live eval: `data/eval_fixtures/patch_sample.txt` сбрасывается автоматически; вручную: `./scripts/reset_eval_patch_fixture.sh`

- Parity eval gate (20 scenarios):
  - `POST /api/eval/run-suite` with payload `{"category":"cursor_parity","limit":20,"persist_report":false}`
  - pass result through `scripts/eval_ci_gate.py`
- Queue lifecycle gates from `/api/ops/agent-runs/metrics`:
  - `stale_queued_runs` and `stale_running_runs` stay near zero under normal load
  - `max_queued_age_seconds` and `max_running_age_seconds` stay below SLA budget
- Confirm stable desktop profile exists:
  - template id `desktop-cursor-parity-stable`

## 7) Clients (optional before tag)

```bash
./scripts/build_clients.sh
# или в release_all:
TERMIT_RELEASE_BUILD_CLIENTS=true ./scripts/release_all.sh
```

- `termit-client`: `npm test` (12 tests)
- `vscode-extension`: `tsc` build
- `termit-desktop`: `vite build` → `dist/`
