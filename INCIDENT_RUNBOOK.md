# Termit Incident Runbook

## Severity Levels

- `SEV-1`: API unavailable or unsafe tool execution detected.
- `SEV-2`: major feature degraded (chat, tasks, tools).
- `SEV-3`: partial degradation with workaround.

## Automated Drill

Run structured checks before manual triage:

```bash
python3 scripts/run_incident_drill.py --api-key <admin-key>
```

Or call API directly:

- `GET /api/ops/readiness` (no auth required)
- `POST /api/ops/incident-drill` (admin API key)

## First 15 Minutes

1. Confirm incident scope (`/health`, `/api/ops/readiness`, `/api/providers/status`).
2. Check recent deploy/config changes (`.env`, model endpoints).
3. Capture failing request samples (status code, endpoint, API key role).
4. Decide severity and assign incident owner.

## Common Failure Patterns

### Provider unavailable

Symptoms:
- `/api/chat` returns provider connection errors.
- stream emits `error` events.

Actions:
- verify Ollama/OpenAI-compatible endpoint health;
- confirm circuit breaker cooldown is not blocking all providers;
- switch fallback model in `.env`.

### Auth/quota failures

Symptoms:
- `401` missing/invalid API key.
- `403` insufficient role.
- `429` daily quota exceeded.

Actions:
- validate `TERMIT_API_KEYS` format `key:quota:role`;
- inspect `GET /api/usage`;
- increase quota or rotate key if needed.

### Tool safety block

Symptoms:
- command endpoint returns blocked/confirm-required.

Actions:
- inspect `/api/tools/audit`;
- require explicit confirmation for risky commands;
- keep dry-run enabled during triage.

## Recovery Checklist

- [ ] Root cause documented.
- [ ] Mitigation applied and verified.
- [ ] Regression tests run (`python -m unittest discover -s tests -v`).
- [ ] User-facing status updated.
- [ ] Post-incident action items logged.
