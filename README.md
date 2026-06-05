# TelegramBotOnSteroids

TelegramBotOnSteroids is being migrated from a Raspberry Pi hosted Telegram torrent bot into a portable Docker Compose stack.

The old bot searched through Jackett and added torrents to qBittorrent. The new direction is to package the bot and its supporting services so the whole setup can move between a Raspberry Pi 5, other Linux hosts, and Windows with Docker Desktop.

## Target Stack

- `telegram-bot`: custom Python Telegram bot.
- `vpn`: VPN network gateway.
- `qbittorrent`: torrent client routed through the VPN service.
- `prowlarr`: preferred long-term indexer manager.
- `jackett`: optional compatibility service while migrating the old bot.
- `watchtower`: optional container update helper.

## Current State

This repository currently contains the old Python bot source plus planning documents for the new Docker-based version.

Start here:

- `docs/PROJECT_OVERVIEW.md`
- `docs/PROJECT_PLAN.md`
- `docs/DOCKER_STACK_PLAN.md`
- `docs/CONFIGURATION_PLAN.md`
- `.env.example`

## Configuration Direction

The bot now loads one root `.env` file for secrets and host-specific settings. Runtime environment variables take precedence over values in `.env`, which keeps Docker Compose and local development using the same configuration model.

Use `.env.example` as the template:

```bash
cp .env.example .env
```

Do not commit real `.env` files.

At startup, the bot validates required Telegram, qBittorrent, and indexer settings by key name only. It does not print secret values. Legacy Jackett JSON config can still be used through `JACKETT_CONFIG_PATH` during migration, but root `.env` is the preferred source.

## Legacy Local Development

Until the Docker migration is implemented, the old bot can still be run in Python:

```bash
python3 -m venv mybotenv
source mybotenv/bin/activate
pip install -r requirements.txt
python -m bot.main
```

On Windows PowerShell:

```powershell
py -m venv mybotenv
.\mybotenv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m bot.main
```

## Tests

```bash
./run_all_tests.sh
# or
PYTHONPATH=. pytest --cov=bot --cov-report=term --cov-report=html tests/
```

On Windows, run tests through the local virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pytest tests
```

Shell hook execution tests are skipped on Windows because `.sh` files are not directly executable there; static hook checks still run.

## Current Migration Status

Phase 1 configuration cleanup is complete for the current bot and helper scripts: Python config loading and post-download scripts now prefer the root `.env` file, with narrow compatibility fallbacks for old env/json locations.

Phase 2 and Phase 3 Docker scaffolding now exists:

- `Dockerfile` builds the Telegram bot image.
- `docker-compose.yml` defines `telegram-bot`, `vpn`, `qbittorrent`, and `prowlarr` as the default stack.
- qBittorrent uses `network_mode: service:vpn`, so its Web UI is published through the `vpn` service.
- `jackett` is available through the `legacy-indexer` profile.
- `watchtower` is available through the `updates` profile.

## Docker Compose Usage

Create a real `.env` from the template and fill in Telegram, qBittorrent, indexer, and VPN values:

```bash
cp .env.example .env
```

Start the default stack:

```bash
docker compose up -d
```

Start with legacy Jackett compatibility:

```bash
docker compose --profile legacy-indexer up -d
```

Start with Watchtower:

```bash
docker compose --profile updates up -d
```

The qBittorrent Web UI is exposed on `QB_WEBUI_PORT` through the `vpn` service. Persistent service data is stored under `data/`. Downloads are mounted from `DOWNLOADS_HOST_PATH` on the host into `DOWNLOADS_PATH` inside the containers; by default this is `./downloads` on the host and `/downloads` in containers. Both `data/` and the default `downloads/` folder are ignored by git.

qBittorrent categories control the final media subfolders:

```env
QB_CATEGORY_MOVIE_PATH=/downloads/Movie
QB_CATEGORY_TV_PATH=/downloads/TV
QB_CATEGORY_OTHERS_PATH=/downloads/Others
```

For example, with `DOWNLOADS_HOST_PATH=D:/Downloads` and `QB_CATEGORY_MOVIE_PATH=/downloads/Movies`, movies are saved under `D:\Downloads\Movies`. On the Raspberry Pi, `DOWNLOADS_HOST_PATH=/var/lib/plexmediaserver/Library/plex_media` maps `/downloads/TV` to `/var/lib/plexmediaserver/Library/plex_media/TV`.

qBittorrent's completion hook should run `/scripts/run_post_download.sh "%N"`. The hook sends the optional Telegram notification and deletes completed torrent entries while keeping downloaded files.

## Indexers

The bot now uses a small indexer abstraction. Prowlarr is preferred when `PROWLARR_API_KEY` is set, using Prowlarr's JSON search API at `${PROWLARR_URL}/api/v1/search`. Prowlarr results may provide magnet links or Prowlarr download URLs; both are accepted by qBittorrent.

Jackett remains available as a legacy fallback when Prowlarr is not configured. Existing Jackett search behavior is preserved, including the temporary `JACKETT_CONFIG_PATH` JSON fallback during migration.

## Bot Status

The `/status` command is being updated for the Docker stack. It now reports qBittorrent API health, Prowlarr reachability, Telegram API reachability, and container-safe disk/RAM/CPU information. Jackett is shown only when configured.
