#!/usr/bin/env bash
# Add ~/.ssh/id_ed25519.pub to GitHub: via API (token) or clipboard + browser.
set -euo pipefail

PUB="${HOME}/.ssh/id_ed25519.pub"
KEY_TITLE="${TERMIT_GITHUB_KEY_TITLE:-Termit $(hostname -s 2>/dev/null || echo Mac)}"

if [[ ! -f "$PUB" ]]; then
  echo "error: missing $PUB — run ./scripts/setup_github_ssh.sh first" >&2
  exit 1
fi

TOKEN="${TERMIT_GITHUB_TOKEN:-${GITHUB_TOKEN:-}}"
if [[ -n "$TOKEN" ]]; then
  KEY_JSON="$(python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))' < "$PUB")"
  TITLE_JSON="$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$KEY_TITLE")"
  BODY="$(printf '{"title":%s,"key":%s}' "$TITLE_JSON" "$KEY_JSON")"
  HTTP="$(curl -sS -o /tmp/termit-gh-key.json -w '%{http_code}' \
    -X POST https://api.github.com/user/keys \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -H "Content-Type: application/json" \
    -d "$BODY")"
  if [[ "$HTTP" == "201" ]]; then
    echo "SSH key added on GitHub (API)."
    ssh -o BatchMode=yes -T git@github.com 2>&1 || true
    exit 0
  fi
  if [[ "$HTTP" == "422" ]] && grep -q 'already in use' /tmp/termit-gh-key.json 2>/dev/null; then
    echo "Key already registered on GitHub."
    exit 0
  fi
  echo "error: GitHub API HTTP $HTTP" >&2
  cat /tmp/termit-gh-key.json >&2
  exit 1
fi

if command -v pbcopy >/dev/null 2>&1; then
  pbcopy < "$PUB"
  echo "Public key copied to clipboard."
else
  echo "Paste this key on GitHub:"
  cat "$PUB"
fi

if command -v open >/dev/null 2>&1; then
  open "https://github.com/settings/ssh/new"
  echo "Opened: https://github.com/settings/ssh/new"
  echo "Title suggestion: $KEY_TITLE"
  echo "Click Add SSH key, then: ssh -T git@github.com && ./scripts/first_push.sh"
else
  echo "Open https://github.com/settings/keys and add the key above."
fi
