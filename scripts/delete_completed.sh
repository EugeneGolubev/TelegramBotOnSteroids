#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BOT_ENV_PATH="$PROJECT_ROOT/bot/.env"
ROOT_ENV_PATH="$PROJECT_ROOT/.env"
SCRIPT_ENV_PATH="$SCRIPT_DIR/.env"

# Load the repo-root .env first; keep old locations as migration fallbacks.
# In Docker, Compose can provide these values directly as environment variables.
if [[ -n "${QB_URL:-}" && -n "${QB_USER:-}" && -n "${QB_PASS:-}" ]]; then
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

HOST="$QB_URL"
USERNAME="$QB_USER"
PASSWORD="$QB_PASS"

# Tools checks
if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required but not installed" >&2
  exit 1
fi

# Temp cookie file with cleanup
COOKIE_FILE="$(mktemp -t qbcookies.XXXXXX)"
trap 'rm -f "$COOKIE_FILE"' EXIT

# Authenticate
curl -fsS -c "$COOKIE_FILE" -d "username=$USERNAME&password=$PASSWORD" "$HOST/api/v2/auth/login" >/dev/null

# Get completed torrents and delete them (but keep files)
completed_hashes=$(curl -fsS -b "$COOKIE_FILE" "$HOST/api/v2/torrents/info" | jq -r '.[] | select(.progress == 1.0) | .hash')

if [[ -z "$completed_hashes" ]]; then
  echo "No completed torrents found."
  exit 0
fi

while read -r hash; do
  [[ -z "$hash" ]] && continue
  echo "😏 Torrent completed: $hash — giving it 15 seconds before deletion..."
  sleep "${QBT_DELETE_DELAY:-15}"
  echo "🔥 Deleting: $hash"
  curl -fsS -X POST -b "$COOKIE_FILE" \
    -d "hashes=$hash&deleteFiles=false" \
    "$HOST/api/v2/torrents/delete" >/dev/null
done <<<"$completed_hashes"
