# Termit Release Checklist

## 1) Pre-release quality

- Run tests: `python -m unittest discover -s tests -v`
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
- Write migration notes for the release (example: `docs/MIGRATION_NOTES_0.3.3.md`)
- Write rollback plan with explicit smoke/health verification

## 6) Cursor parity release gates

- Release smoke profiles:
  - Deterministic core (default): `TERMIT_RELEASE_SMOKE_PROFILE=core ./scripts/release_smoke.sh`
  - Extended suite (nightly/integration): `TERMIT_RELEASE_SMOKE_PROFILE=extended ./scripts/release_smoke.sh`

- Parity eval gate (20 scenarios):
  - `POST /api/eval/run-suite` with payload `{"category":"cursor_parity","limit":20,"persist_report":false}`
  - pass result through `scripts/eval_ci_gate.py`
- Queue lifecycle gates from `/api/ops/agent-runs/metrics`:
  - `stale_queued_runs` and `stale_running_runs` stay near zero under normal load
  - `max_queued_age_seconds` and `max_running_age_seconds` stay below SLA budget
- Confirm stable desktop profile exists:
  - template id `desktop-cursor-parity-stable`
