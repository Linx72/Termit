# Migration Notes 0.3.3

## Scope

This release focuses on Cursor parity for autonomous coding flows:
- runtime queue hardening,
- deterministic tool-loop behavior,
- desktop tape transparency,
- parity eval quality gates,
- stable default profile path.

## Configuration changes

- New env var: `TERMIT_AGENT_QUEUE_STUCK_TIMEOUT_SECONDS` (default `120`).
  - Purpose: threshold used for queue watchdog metrics visibility (`stale_*` counters and max dwell).
  - Recommended range: `60..300` depending on typical run duration.

## API / metrics changes

- `GET /api/ops/agent-runs/metrics` now includes:
  - `stale_queued_runs`
  - `stale_running_runs`
  - `max_queued_age_seconds`
  - `max_running_age_seconds`
  - `queue_stuck_timeout_seconds`

No breaking changes for existing fields.

## Desktop behavior changes

- Default template path now prefers `desktop-cursor-parity-stable`.
- Fallback remains `web-app-vite` if stable template is unavailable.
- Activity tape now appends heartbeat lines while a run is active.

## Eval / CI changes

- Added parity eval category `cursor_parity` with 20 scenarios (CP1..CP20).
- CI and release smoke gate now execute parity eval before full suite.
- Total scenario count in `data/eval_scenarios.json` increased to `74`.

## Operator checks after upgrade

1. Confirm health:
   - `GET /health` => 200
   - `GET /healthz` => 200
2. Confirm queue metrics endpoint:
   - `GET /api/ops/agent-runs/metrics` => 200 and new fields present
3. Run smoke:
   - `./scripts/smoke_http.sh`
4. Run parity gate:
   - `curl -s -X POST http://127.0.0.1:8765/api/eval/run-suite -H 'Content-Type: application/json' -d '{"category":"cursor_parity","limit":20,"persist_report":false}' | ./.venv/bin/python scripts/eval_ci_gate.py`
