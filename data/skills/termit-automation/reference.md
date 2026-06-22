# Termit Automation — reference

## PATCH examples

Disable all background automation:

```bash
curl -sf -X PATCH http://127.0.0.1:8765/api/ops/automation \
  -H 'Content-Type: application/json' \
  -d '{"automatic_mode_enabled":false}'
```

Disable only Stage1 and external weekly eval cron:

```bash
curl -sf -X PATCH http://127.0.0.1:8765/api/ops/automation \
  -H 'Content-Type: application/json' \
  -d '{"toggles":{"stage1_schedule":false,"weekly_eval_cron":false}}'
```

With auth:

```bash
curl -sf -H "X-API-Key: dev-key" ...
```

## Response shape

```json
{
  "env_path": "/path/to/Termit/.env",
  "automatic_mode_enabled": true,
  "toggles": [
    {
      "toggle_id": "stage1_schedule",
      "env_key": "TERMIT_STAGE1_SCHEDULE_ENABLED",
      "enabled": true,
      "requires_restart": false
    }
  ],
  "schedulers": {
    "stage1": { "enabled": true, "thread_alive": true },
    "daily_improvement": { "enabled": true, "thread_alive": true }
  }
}
```

## Env keys (do_all_automatic defaults)

| Env variable | Default after automatic |
|--------------|-------------------------|
| `TERMIT_STAGE1_SCHEDULE_ENABLED` | true |
| `TERMIT_STAGE1_SCHEDULE_BASE_MODEL` | (empty → `TERMIT_TEACHER_MODEL`) |
| `TERMIT_TEACHER_MODEL` | ollama:deepseek-coder |
| `TERMIT_CODE_MODEL` | ollama:termit-core-ft |
| `TERMIT_DAILY_IMPROVEMENT_ENABLED` | true |
| `TERMIT_AGENT_SCHEDULES_ENABLED` | true |
| `TERMIT_AGENT_MAINTENANCE_ENABLED` | true |
| `TERMIT_RETRIEVAL_AUTO_REINDEX` | true |
| `TERMIT_FINETUNE_AUTO_CAPTURE_SIGNALS` | true |
| `TERMIT_AUTO_START_OLLAMA` | true |
| `TERMIT_EVAL_CI_LIMIT` | 53 |

Override env file path: `TERMIT_ENV_FILE=/custom/.env`.

## Crontab markers

| Marker | Script |
|--------|--------|
| `# termit-weekly-eval` | `scripts/weekly_eval.sh` (Mon 04:00 local) |
| `# termit-daily-improvement` | `scripts/daily_improvement.sh` (02:05 local) |

Removing a toggle with `weekly_eval_cron: false` strips lines containing the marker from `crontab -l`.

## Status endpoints (related)

```bash
curl -s http://127.0.0.1:8765/api/finetune/pipeline/stage1-scheduler/status | python3 -m json.tool
curl -s http://127.0.0.1:8765/api/ops/daily-improvement/status | python3 -m json.tool
```

## Uninstall API autostart

```bash
./scripts/uninstall_launch_agent.sh
```

LaunchAgent label: `com.termit.server` → `http://127.0.0.1:8765`.

## Desktop SDK

```typescript
import { getAutomationPrefs, updateAutomationPrefs } from "@termit/client";

const prefs = await getAutomationPrefs(client);
await updateAutomationPrefs(client, { automatic_mode_enabled: false });
```

## Tests

```bash
python3 -m unittest tests.test_automation_prefs -q
```
