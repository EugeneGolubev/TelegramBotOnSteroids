# Docker Stack Plan

## Recommendation

Use one Docker Compose project with several containers.

This gives the user one operational unit while preserving clean boundaries between services. Each service can be updated, restarted, logged, and replaced independently.

## Services

### telegram-bot

Purpose:

- Run the custom Python Telegram bot.
- Talk to qBittorrent API.
- Talk to Prowlarr by default, with Jackett as a legacy fallback.

Networking:

- Normal Compose network.
- Does not need to run behind VPN by default.

Persistence:

- Optional bot data under `data/bot/`.
- Reads settings from root `.env`.

### vpn

Purpose:

- Provide VPN network namespace for torrent traffic.

Networking:

- Owns the qBittorrent network path.
- Exposes qBittorrent Web UI ports if qBittorrent uses `network_mode: service:vpn`.

Persistence:

- VPN config under `data/vpn/` if required by the selected image/provider.

Selected initial image:

- `qmcgaw/gluetun:latest`
- This keeps the stack provider/protocol-flexible while the real VPN provider is still an environment-specific choice.
- Fill Gluetun-compatible values in `.env`, such as `VPN_PROVIDER`, `VPN_TYPE`, `VPN_USERNAME`, `VPN_PASSWORD`, or WireGuard keys.

### qbittorrent

Purpose:

- Download torrents.
- Provide API used by the bot.

Networking:

- Route through VPN with `network_mode: service:vpn`.
- Publish qBittorrent Web UI through the VPN service.

Persistence:

- Config under `data/qbittorrent/`.
- Downloads under `downloads/`.

Selected initial image:

- `lscr.io/linuxserver/qbittorrent:latest`

### prowlarr

Purpose:

- Preferred long-term indexer manager.
- Provides Torznab-style indexer endpoints.
- Used by the bot when `PROWLARR_API_KEY` is configured.

Networking:

- Normal Compose network.
- Can be routed through VPN later if a real indexer need appears.

Persistence:

- Config under `data/prowlarr/`.

Selected initial image:

- `lscr.io/linuxserver/prowlarr:latest`

### jackett

Purpose:

- Optional compatibility service for the old bot while migration is happening.
- Used by the bot only when Prowlarr is not configured.

Networking:

- Normal Compose network.

Persistence:

- Config under `data/jackett/`.

Default state:

- Optional profile, not necessarily always enabled.

Selected initial image:

- `lscr.io/linuxserver/jackett:latest`

### watchtower

Purpose:

- Container update automation or notifications.

Networking:

- Normal Docker access.

Security note:

- Requires Docker socket access, so it should be configured deliberately.
- Consider notification-only mode before enabling automatic updates.

Selected initial image:

- `containrrr/watchtower:latest`

## Compose Profiles

Recommended profiles:

- default: `telegram-bot`, `vpn`, `qbittorrent`, `prowlarr`
- `legacy-indexer`: adds `jackett`
- `updates`: adds `watchtower`

Current Compose state:

- `docker-compose.yml` implements these profiles.
- qBittorrent uses `network_mode: service:vpn`.
- qBittorrent Web UI and torrent ports are published on the `vpn` service because qBittorrent shares that network namespace.

## Network Model

Preferred model:

```text
telegram-bot -> qbittorrent API through vpn service published port
telegram-bot -> prowlarr API on Compose network
qbittorrent -> internet through vpn
prowlarr -> internet directly unless routed later
```

This avoids forcing all services through VPN and keeps the torrent traffic protected.

## Data Model

Suggested local folders:

```text
data/
  bot/
  vpn/
  qbittorrent/
  prowlarr/
  jackett/
downloads/
```

These folders should be ignored by git. A host migration should preserve `.env`, `data/`, and `downloads/`.

## Open Decisions

- VPN provider and protocol values for Gluetun.
- Whether to keep Jackett for the first Docker version or migrate directly to Prowlarr.
- Whether Watchtower should auto-update or only notify.
- Whether Plex remains host-installed or becomes part of the Compose stack later.
