#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_LOG_FILE="/config/post_download.log"
if [[ ! -d /config ]]; then
  DEFAULT_LOG_FILE="$SCRIPT_DIR/post_download.log"
fi
LOG_FILE="${POST_DOWNLOAD_LOG_FILE:-$DEFAULT_LOG_FILE}"

log() {
  local message="$1"
  if ! echo "$(date) $message" >> "$LOG_FILE" 2>/dev/null; then
    echo "$(date) $message" >&2
  fi
}

"$SCRIPT_DIR/notify_complete.sh" "${1:-Unknown}" || log "[run_post_download] Notification failed for '${1:-Unknown}'"

# Optional: Wait for file to be fully flushed
sleep 10

"$SCRIPT_DIR/delete_completed.sh"

log "[run_post_download] Finished ${1:-Unknown}"
