# Git sync (Termit)

Multi-machine workflow lives in **[SYNC_WORKFLOW.md](../SYNC_WORKFLOW.md)** (Russian-friendly).

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup_new_machine.sh` | venv, pip, `.env`, verify remote |
| `scripts/sync_start.sh` | `fetch` + `pull --rebase` + status |
| `scripts/sync_finish.sh` | `add`, `commit`, `push` |

## Optional repo-local aliases

Edit `.git/config` in this clone (not `--global`):

```ini
[alias]
  up = pull --rebase origin main
  save = !f(){ git add -A && git commit -m \"${1:-wip}\" && git push origin main; }; f
```

## First push checklist

1. SSH key or HTTPS PAT configured
2. `git push -u origin main`
3. `git push origin v0.2.0` (if tag exists locally)
