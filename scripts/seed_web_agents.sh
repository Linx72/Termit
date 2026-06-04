#!/usr/bin/env bash
# Create or reuse agents from web/online templates (allow_online=true in JSON).
set -euo pipefail

BASE="${TERMIT_API_URL:-http://127.0.0.1:8765}"

for template in web-app-vite research-fast research-deep online-project-manager; do
  echo "== ensure-agent: $template =="
  curl -fsS -X POST "${BASE}/api/projects/agent-templates/${template}/ensure-agent" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d.get('name'), d.get('agent_id'), 'allow_online=', d.get('allow_online'))
" || echo "warning: failed for $template" >&2
done

echo "Agents ready."
