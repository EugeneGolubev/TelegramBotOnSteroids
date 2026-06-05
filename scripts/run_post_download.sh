#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/post_download.log"

"$SCRIPT_DIR/notify_complete.sh" "${1:-Unknown}"

# Optional: Wait for file to be fully flushed
sleep 10

"$SCRIPT_DIR/delete_completed.sh"

{
  echo "$(date): Finished ${1:-Unknown}"
} >> "$LOG_FILE"
