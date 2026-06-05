# Configuration Plan

## Goal

Use one root `.env` file for secrets and host-specific settings. Commit only `.env.example`.

The project should not require editing source code or committing secret files when moved between Raspberry Pi, Windows, Linux, or macOS.

## Config Sources

Preferred:

1. Runtime environment variables.
2. Root `.env` loaded by Docker Compose and local development.

Temporary compatibility:

- Existing `bot/.env`, `scripts/.env`, and Jackett JSON config may remain during migration but should not be the long-term default.

Current implementation:

- `bot/config.py` loads the repo-root `.env` file with `python-dotenv` and does not override already-set runtime environment variables.
- `bot/main.py` validates startup config before building the Telegram application.
- `scripts/notify_complete.sh` and `scripts/delete_completed.sh` use runtime environment variables when Compose provides them, then fall back to root `.env`, `bot/.env`, and `scripts/.env`.
- `bot/jackett.py` reads Jackett settings from env first. If Jackett API settings are missing, it can read the JSON file named by `JACKETT_CONFIG_PATH` as a temporary migration fallback.
- `docker-compose.yml` uses root `.env` values for the bot, Gluetun VPN gateway, qBittorrent, Prowlarr, optional Jackett, and optional Watchtower.
- `bot/indexers.py` prefers Prowlarr search when `PROWLARR_API_KEY` is set and falls back to Jackett only when Prowlarr is not configured.
- `bot/torrent.py` creates or updates qBittorrent category save paths before adding a torrent.

## Required Secret Values

- `BOT_TOKEN`
- `AUTHORIZED_USER_ID`
- `ALLOWED_CHAT_ID`
- `QB_USER`
- `QB_PASS`
- VPN provider credentials or WireGuard/OpenVPN config values
- Indexer API keys, such as `PROWLARR_API_KEY` or `JACKETT_API_KEY`

## Required Non-Secret Values

- `QB_URL`
- `PROWLARR_URL` or `JACKETT_URL`
- `DOWNLOADS_HOST_PATH`
- `DOWNLOADS_PATH`
- `QB_AUTORUN_QB_URL`
- `QB_CATEGORY_MOVIE_PATH`
- `QB_CATEGORY_TV_PATH`
- `QB_CATEGORY_OTHERS_PATH`
- Timezone, such as `TZ`

## Docker Compose Values

Common non-secret Compose values:

- `PUID`
- `PGID`
- `QB_WEBUI_PORT`
- `QB_TORRENT_PORT`
- `PROWLARR_PORT`
- `JACKETT_PORT`
- `WATCHTOWER_CLEANUP`
- `WATCHTOWER_POLL_INTERVAL`

VPN values are Gluetun-oriented placeholders:

- `VPN_PROVIDER`
- `VPN_TYPE`
- `VPN_USERNAME`
- `VPN_PASSWORD`
- `VPN_WIREGUARD_PRIVATE_KEY`
- `VPN_WIREGUARD_ADDRESSES`
- `VPN_WIREGUARD_MTU`
- `VPN_SERVER_COUNTRIES`
- `VPN_FIREWALL_OUTBOUND_SUBNETS`
- `VPN_PORT_FORWARDING`
- `VPN_PORT_FORWARDING_PROVIDER`
- `VPN_PORT_FORWARDING_STATUS_FILE`
- `VPN_PORT_FORWARDING_UP_COMMAND`

Only fill values that match the selected VPN provider and protocol. Do not commit the real `.env`.

For Proton VPN, WireGuard is the preferred speed path. `VPN_USERNAME` and `VPN_PASSWORD` are OpenVPN credentials. They are not used as `VPN_WIREGUARD_PRIVATE_KEY` or `VPN_WIREGUARD_ADDRESSES`; those values come from a Proton manual WireGuard config:

```ini
[Interface]
PrivateKey = ...
Address = 10.2.0.2/32
```

If Proton NAT-PMP port forwarding is enabled in the generated WireGuard config, set:

```env
VPN_PORT_FORWARDING=on
VPN_PORT_FORWARDING_PROVIDER=protonvpn
```

Gluetun writes the active forwarded port to `VPN_PORT_FORWARDING_STATUS_FILE`. If `VPN_PORT_FORWARDING_UP_COMMAND` is configured to update qBittorrent, qBittorrent must allow Web UI access from localhost because it shares the VPN container network namespace.

After changing `.env`, recreate the affected containers rather than rebuilding images:

```bash
docker compose up -d --force-recreate vpn qbittorrent
docker compose logs --tail=120 vpn | grep -Ei 'wireguard|openvpn|proton|port forwarding'
```

Use `docker compose up -d --build` only when the bot image itself changed, such as after editing the `Dockerfile`, Python dependencies, or application code that should be baked into the image.

## Naming Guidelines

- Use uppercase snake case.
- Prefix service-specific settings with the service name where useful.
- Keep values platform-neutral where possible.

Examples:

```env
QB_URL=http://vpn:8080
PROWLARR_URL=http://prowlarr:9696
PROWLARR_DEFAULT_INDEXER=all
DOWNLOADS_HOST_PATH=./downloads
DOWNLOADS_PATH=/downloads
QB_AUTORUN_QB_URL=http://127.0.0.1:8080
QB_CATEGORY_MOVIE_PATH=/downloads/Movie
QB_CATEGORY_TV_PATH=/downloads/TV
QB_CATEGORY_OTHERS_PATH=/downloads/Others
```

Prowlarr search uses `${PROWLARR_URL}/api/v1/search` with `PROWLARR_API_KEY` sent as the `X-Api-Key` header. `PROWLARR_DEFAULT_INDEXER` is kept in the environment template for compatibility while the migration settles, but current bot search uses Prowlarr's enabled indexers through its search API. Jackett uses `JACKETT_DEFAULT_INDEXER` the same way it did before migration.

`DOWNLOADS_HOST_PATH` is the host directory mounted into containers. `DOWNLOADS_PATH` is the in-container path and should usually stay `/downloads`. Category paths should also use in-container paths, so the same category config works on Windows, Linux, macOS, and Raspberry Pi hosts.

`QB_AUTORUN_QB_URL` is used only by the qBittorrent completion hook running inside the qBittorrent container. It defaults to `http://127.0.0.1:8080` because qBittorrent can reach its own Web API there.

## Validation

The bot should validate configuration at startup and fail clearly when required values are missing.

Validation should:

- Name missing keys.
- Avoid printing secret values.
- Distinguish required and optional settings.
- Be covered by tests.

Implemented startup validation currently checks:

- `BOT_TOKEN`
- `AUTHORIZED_USER_ID`
- `ALLOWED_CHAT_ID`
- `QB_USER`
- `QB_PASS`
- at least one indexer API key: `PROWLARR_API_KEY` or `JACKETT_API_KEY`

The validation error names missing or invalid keys only. It does not print token, password, or API key values.

## Git Ignore Policy

Ignore:

- `.env`
- `.env.*` except `.env.example`
- `data/`
- `downloads/`
- logs, caches, coverage output, and local virtualenvs

Commit:

- `.env.example`
- Docker and Compose files
- docs
- source code
- tests
