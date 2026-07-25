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

When changing VPN settings in `.env`, recreate the affected containers so Docker Compose injects the new environment:

```bash
docker compose up -d --force-recreate vpn qbittorrent
docker compose logs --tail=120 vpn | grep -Ei 'wireguard|openvpn|proton|port forwarding'
```

Rebuilding is not needed for `.env` changes. Use `docker compose up -d --build` only after changing the `Dockerfile`, Python dependencies, or bot code that should be baked into the image.

## Proton VPN Notes

For Proton VPN, OpenVPN works but WireGuard is usually the faster option, especially on Raspberry Pi hardware. Generate a Proton manual WireGuard config with **NAT-PMP (Port Forwarding)** enabled if you want better torrent peer connectivity. Map the generated config into `.env` like this:

```env
VPN_PROVIDER=protonvpn
VPN_TYPE=wireguard
VPN_WIREGUARD_PRIVATE_KEY=<Interface PrivateKey>
VPN_WIREGUARD_ADDRESSES=<Interface Address, for example 10.2.0.2/32>
VPN_PORT_FORWARDING=on
VPN_PORT_FORWARDING_PROVIDER=protonvpn
VPN_PORT_FORWARDING_STATUS_FILE=/tmp/gluetun/forwarded_port
VPN_PORT_FORWARDING_UP_COMMAND=/bin/sh -c 'wget -qO- --retry-connrefused --post-data "json={\"listen_port\":{{PORT}},\"current_network_interface\":\"{{VPN_INTERFACE}}\",\"current_interface_address\":\"10.2.0.2\",\"random_port\":false,\"upnp\":false}" http://127.0.0.1:8080/api/v2/app/setPreferences'
VPN_PORT_FORWARDING_DOWN_COMMAND=/bin/sh -c 'wget -qO- --retry-connrefused --post-data "json={\"listen_port\":0,\"current_network_interface\":\"lo\"}" http://127.0.0.1:8080/api/v2/app/setPreferences'
```

`VPN_USERNAME` and `VPN_PASSWORD` are for OpenVPN credentials; they are not the WireGuard private key or address. Treat `VPN_WIREGUARD_PRIVATE_KEY` like a password and never commit the real value.

If Gluetun starts correctly with WireGuard, the VPN logs should mention `[wireguard]`, not `[openvpn]`. If the logs still show OpenVPN after editing `.env`, force-recreate the services as shown above and verify you are running the command from the Linux host's project folder.

Gluetun writes Proton's forwarded port to `VPN_PORT_FORWARDING_STATUS_FILE`, which defaults to `/tmp/gluetun/forwarded_port`. The UP command copies the dynamic port into qBittorrent and binds its TCP and UDP sockets to the WireGuard address. The DOWN command moves qBittorrent to loopback while the tunnel is unavailable. In qBittorrent, enable **Web UI > Bypass authentication for clients on localhost** so Gluetun can call the API through their shared network namespace.

The example assumes Proton assigned `Address = 10.2.0.2/32`. If the generated WireGuard config uses another address, use that address in both `VPN_WIREGUARD_ADDRESSES` and `current_interface_address`. Binding only to the `tun0` interface can update qBittorrent's saved port without opening a listening socket; the explicit address avoids that failure.

Do not publish a fixed qBittorrent peer port such as `6881` on the Docker host when using Proton's dynamic port forwarding. Tunnel traffic enters through Gluetun on the provider-assigned port, not through a Docker host mapping. The qBittorrent Web UI remains published through the `vpn` service on port `8080`.

Verify that Proton's forwarded port, qBittorrent's preference, and its active socket all match:

```bash
docker exec vpn cat /tmp/gluetun/forwarded_port
docker exec vpn sh -c \
  'wget -qO- http://127.0.0.1:8080/api/v2/app/preferences | grep -o "\"listen_port\":[0-9]*"'
docker exec qbittorrent sh -c \
  'netstat -lntup 2>/dev/null | grep "10.2.0.2"'
```

The qBittorrent application log is under `/config/qBittorrent/logs/qbittorrent.log`. Torrent download URLs in that log may include Prowlarr API keys, so redact URLs before sharing logs and rotate any exposed key.

qBittorrent categories control the final media subfolders:

```env
QB_CATEGORY_MOVIE_PATH=/downloads/Movie
QB_CATEGORY_TV_PATH=/downloads/TV
QB_CATEGORY_OTHERS_PATH=/downloads/Others
```

For example, with `DOWNLOADS_HOST_PATH=D:/Downloads` and `QB_CATEGORY_MOVIE_PATH=/downloads/Movies`, movies are saved under `D:\Downloads\Movies`. On the Raspberry Pi, `DOWNLOADS_HOST_PATH=/var/lib/plexmediaserver/Library/plex_media` maps `/downloads/TV` to `/var/lib/plexmediaserver/Library/plex_media/TV`.

In qBittorrent Web UI, configure **Options > Downloads > Saving Management** so category paths are actually used:

```text
Default Torrent Management Mode: Automatic
When Torrent Category changed: Relocate torrent
When Category Save Path changed: Relocate torrent
Default Save Path: /downloads
```

If using manual torrent management instead, enable **Use Category paths in Manual Mode**.

qBittorrent's completion hook should run `bash /scripts/run_post_download.sh "%N" "%I"`. The hook sends the optional Telegram notification and deletes the completed torrent entry while keeping downloaded files.

## Indexers

The bot now uses a small indexer abstraction. Prowlarr is preferred when `PROWLARR_API_KEY` is set, using Prowlarr's JSON search API at `${PROWLARR_URL}/api/v1/search`. Prowlarr results may provide magnet links or Prowlarr download URLs; both are accepted by qBittorrent.

Jackett remains available as a legacy fallback when Prowlarr is not configured. Existing Jackett search behavior is preserved, including the temporary `JACKETT_CONFIG_PATH` JSON fallback during migration.

## Bot Status

The `/status` command is being updated for the Docker stack. It now reports qBittorrent API health, Prowlarr reachability, Telegram API reachability, and container-safe disk/RAM/CPU information. Jackett is shown only when configured.
