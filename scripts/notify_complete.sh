#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BOT_ENV_PATH="$PROJECT_ROOT/bot/.env"
ROOT_ENV_PATH="$PROJECT_ROOT/.env"
SCRIPT_ENV_PATH="$SCRIPT_DIR/.env"

# Load the repo-root .env first; keep old locations as migration fallbacks.
# In Docker, Compose can provide these values directly as environment variables.
if [[ -n "${BOT_TOKEN:-}" && -n "${NOTIFY_CHAT_ID:-${ALLOWED_CHAT_ID:-}}" ]]; then
    :
elif [ -f "$ROOT_ENV_PATH" ]; then
    source "$ROOT_ENV_PATH"
elif [ -f "$BOT_ENV_PATH" ]; then
    source "$BOT_ENV_PATH"
elif [ -f "$SCRIPT_ENV_PATH" ]; then
    source "$SCRIPT_ENV_PATH"
else
    echo "❌ .env file not found in:"
    echo "   $ROOT_ENV_PATH"
    echo "   $BOT_ENV_PATH"
    echo "   $SCRIPT_ENV_PATH"
    exit 1
fi

BOT_TOKEN="${BOT_TOKEN:-}"
# Prefer NOTIFY_CHAT_ID; if not set, fall back to ALLOWED_CHAT_ID
CHAT_ID="${NOTIFY_CHAT_ID:-${ALLOWED_CHAT_ID:-}}"

TORRENT_NAME="${1:-Unknown}"
LOG_FILE="$SCRIPT_DIR/post_download.log"

if [[ -z "${BOT_TOKEN}" || -z "${CHAT_ID}" ]]; then
  echo "$(date) [notify_complete] Missing BOT_TOKEN or NOTIFY_CHAT_ID/ALLOWED_CHAT_ID" >> "$LOG_FILE"
  exit 0
fi

MESSAGE="🔥 Torrent completed: ${TORRENT_NAME}"

# Use url-encoding for safety
curl -fsS -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d "chat_id=${CHAT_ID}" \
  --data-urlencode "text=${MESSAGE}" >/dev/null

echo "$(date) [notify_complete] Notified ${CHAT_ID} about '${TORRENT_NAME}'" >> "$LOG_FILE"
