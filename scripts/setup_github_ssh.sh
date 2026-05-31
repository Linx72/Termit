#!/usr/bin/env bash
# Generate GitHub SSH key if missing and print setup steps.
set -euo pipefail

KEY="${HOME}/.ssh/id_ed25519"
PUB="${KEY}.pub"

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"

if [[ ! -f "$KEY" ]]; then
  ssh-keygen -t ed25519 -C "termit@$(hostname -s 2>/dev/null || echo local)" -f "$KEY" -N ""
  echo "Created SSH key: $PUB"
else
  echo "SSH key already exists: $PUB"
fi

echo ""
echo "Add this public key at https://github.com/settings/keys :"
echo ""
cat "$PUB"
echo ""
echo "Then run:"
echo "  ssh -T git@github.com"
echo "  $(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/first_push.sh"
