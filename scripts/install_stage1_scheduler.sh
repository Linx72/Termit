#!/usr/bin/env bash
# Install one of the Stage1 scheduler options: builtin | launchd | cron | github
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:-}"

usage() {
  cat <<EOF
Usage: $(basename "$0") <mode>

Modes:
  builtin   Print env vars to enable the built-in Termit scheduler
  launchd   Install macOS LaunchAgent (weekly Monday 03:00 local time via API call)
  cron      Install user crontab entry (weekly Monday 03:00)
  github    Print GitHub Actions setup instructions
  all       Show all options

Shared env file (optional):
  ${ROOT}/deploy/schedulers/stage1-weekly.env
EOF
}

render_launchd() {
  local env_file="${ROOT}/deploy/schedulers/stage1-weekly.env"
  if [[ ! -f "${env_file}" ]]; then
    cp "${ROOT}/deploy/schedulers/stage1-weekly.env.example" "${env_file}"
    echo "Created ${env_file} from example."
  fi
  local plist_path="${HOME}/Library/LaunchAgents/com.termit.stage1-weekly.plist"
  local log_dir="${HOME}/Library/Logs"
  mkdir -p "${HOME}/Library/LaunchAgents" "${log_dir}"
  sed \
    -e "s|@REPO_ROOT@|${ROOT}|g" \
    -e "s|@LOG_DIR@|${log_dir}|g" \
    "${ROOT}/deploy/schedulers/launchd/com.termit.stage1-weekly.plist.template" > "${plist_path}"
  launchctl bootout "gui/${UID}/com.termit.stage1-weekly" 2>/dev/null || true
  launchctl bootstrap "gui/${UID}" "${plist_path}"
  launchctl enable "gui/${UID}/com.termit.stage1-weekly"
  echo "Installed LaunchAgent: ${plist_path}"
  echo "Run now: launchctl kickstart -k gui/${UID}/com.termit.stage1-weekly"
}

install_cron() {
  local env_file="${ROOT}/deploy/schedulers/stage1-weekly.env"
  if [[ ! -f "${env_file}" ]]; then
    cp "${ROOT}/deploy/schedulers/stage1-weekly.env.example" "${env_file}"
    echo "Created ${env_file} from example."
  fi
  local marker="# termit-stage1-weekly"
  local cmd="${ROOT}/scripts/stage1_weekly.sh >> ${HOME}/Library/Logs/termit-stage1-weekly.cron.log 2>&1"
  if [[ "$(uname -s)" == "Linux" ]]; then
    cmd="${ROOT}/scripts/stage1_weekly.sh >> ${HOME}/termit-stage1-weekly.cron.log 2>&1"
  fi
  local line="0 3 * * 1 ${cmd} ${marker}"
  (crontab -l 2>/dev/null | grep -v "${marker}"; echo "${line}") | crontab -
  echo "Installed user crontab entry:"
  echo "  ${line}"
}

show_builtin() {
  cat <<EOF
Built-in scheduler (runs inside Termit process):

Add to .env:
  TERMIT_STAGE1_SCHEDULE_ENABLED=true
  TERMIT_STAGE1_SCHEDULE_WEEKDAY=0      # Monday (Python weekday)
  TERMIT_STAGE1_SCHEDULE_HOUR=3         # UTC
  TERMIT_STAGE1_SCHEDULE_MINUTE=0
  TERMIT_STAGE1_SCHEDULE_MIN_SAMPLES=10

Restart Termit, then check:
  GET /api/finetune/pipeline/stage1-scheduler/status
  POST /api/finetune/pipeline/stage1-scheduler/trigger
EOF
}

show_github() {
  cat <<EOF
GitHub Actions scheduler:

1. Set repository secrets:
   TERMIT_URL=https://your-termit-host
   TERMIT_API_KEY=your-admin-or-operator-key

2. Optional repository variable:
   TERMIT_STAGE1_GHA_ENABLED=true

3. Workflow file already included:
   .github/workflows/stage1-weekly.yml

4. Manual run:
   GitHub -> Actions -> Stage1 weekly pipeline -> Run workflow
EOF
}

case "${MODE}" in
  builtin)
    show_builtin
    ;;
  launchd)
    if [[ "$(uname -s)" != "Darwin" ]]; then
      echo "launchd mode is macOS only." >&2
      exit 1
    fi
    render_launchd
    ;;
  cron)
    install_cron
    ;;
  github)
    show_github
    ;;
  all)
    show_builtin
    echo
    show_github
    echo
    echo "External schedulers use: ${ROOT}/scripts/stage1_weekly.sh"
    echo "Install with: $0 launchd   (macOS)  or  $0 cron"
    ;;
  *)
    usage
    exit 1
    ;;
esac
