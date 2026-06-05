# Project Plan

## Phase 0: Documentation and Direction

Status: in progress

Goals:

- Capture the Docker Compose architecture decision.
- Capture the portable configuration policy.
- Add planning documents for future agents and coding sessions.
- Keep the old bot code intact until the migration work starts.

Deliverables:

- `docs/PROJECT_OVERVIEW.md`
- `docs/DOCKER_STACK_PLAN.md`
- `docs/CONFIGURATION_PLAN.md`
- `docs/PROJECT_PLAN.md`
- `.env.example`
- updated `AGENTS.md`

## Phase 1: Configuration Cleanup

Status: implemented for the current bot and helper scripts

Goals:

- Move toward one root `.env` file.
- Remove dependency on scattered files like `bot/.env`, `scripts/.env`, and `/opt/telegrambot/config.json`.
- Keep backward compatibility where useful during migration.
- Add startup validation for required settings.

Planned actions:

1. Audit all config reads in `bot/` and `scripts/`. Done.
2. Define a single config schema. Done in `bot/config.py`.
3. Add `.env.example` with all supported keys. Done for current bot, qBittorrent, Prowlarr, Jackett, script hooks, VPN placeholders, and Watchtower.
4. Update Python config loading to read root `.env`. Done; runtime env vars still take precedence.
5. Update scripts to read root `.env`. Done; old `bot/.env` and `scripts/.env` remain fallback-only during migration.
6. Add tests for required and optional settings. Done for config behavior, Jackett fallback, and script env-source ordering.

Implementation notes:

- `bot/main.py` validates startup settings through `bot.config.validate_settings`.
- `bot/torrent.py` reads qBittorrent settings at call time so tests and Compose env changes are respected.
- `bot/jackett.py` reads env-first settings and uses legacy JSON only as a migration fallback.
- Validation names missing or invalid keys without printing secret values.
- The old `/opt/telegrambot/config.json` default has been removed.

## Phase 2: Bot Container

Status: implemented with Phase 3 scaffolding

Goals:

- Run the Telegram bot in a Docker container.
- Keep current bot behavior working.
- Support Linux ARM64 for Raspberry Pi 5 and common desktop platforms.

Planned actions:

1. Add `Dockerfile`. Done.
2. Add `.dockerignore`. Done.
3. Add bot service to `docker-compose.yml`. Done.
4. Add health/logging basics. Logging uses container stdout/stderr for now; health checks remain future work.
5. Document local and Pi run commands. Done in `README.md`.
6. Verify that the bot can reach host or Compose services. Compose config validation is the current smoke test; live service startup still requires real `.env` and VPN settings.

## Phase 3: Support Stack Containers

Status: implemented as initial Compose stack

Goals:

- Add qBittorrent, Prowlarr, VPN, optional Jackett, and Watchtower.
- Keep qBittorrent network traffic behind VPN.
- Persist service configuration and downloads outside containers.

Planned actions:

1. Choose base images for each service. Done: `qmcgaw/gluetun`, LinuxServer qBittorrent/Prowlarr/Jackett, and `containrrr/watchtower`.
2. Add named services to Compose. Done.
3. Add volumes under `data/` and `downloads/`. Done.
4. Route qBittorrent with `network_mode: service:vpn`. Done.
5. Expose needed web UI ports through the VPN service where required. Done for qBittorrent.
6. Document first-run setup and migration from existing Pi services. Basic first-run docs are in `README.md`; detailed Pi migration notes remain Phase 6 work.

Implementation notes:

- Default services are `telegram-bot`, `vpn`, `qbittorrent`, and `prowlarr`.
- `jackett` is behind the `legacy-indexer` profile.
- `watchtower` is behind the `updates` profile.
- qBittorrent has no direct published ports because it shares the VPN container network namespace.
- VPN settings are placeholder-friendly and currently target Gluetun; the user must fill provider/protocol-specific values in `.env`.
- Proton VPN speed tuning is documented: prefer WireGuard over OpenVPN, use Proton manual WireGuard `PrivateKey`/`Address` values rather than OpenVPN credentials, enable NAT-PMP port forwarding when needed, and force-recreate `vpn`/`qbittorrent` after `.env` changes.
- `DOWNLOADS_HOST_PATH` controls the host download mount while containers use `/downloads`.
- qBittorrent receives the environment needed by post-download hooks, including `QB_AUTORUN_QB_URL`, qBittorrent credentials, Telegram notification settings, and `QBT_DELETE_DELAY`.

## Phase 4: Indexer Migration

Status: implemented for Prowlarr-first search with Jackett fallback

Goals:

- Prefer Prowlarr as the long-term indexer manager.
- Keep Jackett only as temporary compatibility if needed.

Planned actions:

1. Decide whether the bot should talk directly to Prowlarr. Done: the bot uses Prowlarr's JSON search API.
2. Add a provider abstraction if needed. Done in `bot/indexers.py`.
3. Update search result normalization. Done; handlers still receive `title`, `size`, `seeders`, `tracker`, and `magnet`.
4. Add tests for Prowlarr and/or Jackett behavior. Done in `tests/test_indexers.py`.
5. Remove Jackett from the default stack when no longer needed. Not done; Jackett remains optional through the `legacy-indexer` Compose profile.

Implementation notes:

- Prowlarr is selected when `PROWLARR_API_KEY` is present.
- Jackett is selected when Prowlarr is not configured and Jackett settings are available, including the temporary legacy JSON fallback.
- `bot.handlers` now imports search through `bot.indexers` instead of directly from `bot.jackett`.
- The Prowlarr endpoint is `${PROWLARR_URL}/api/v1/search` with the API key sent in the `X-Api-Key` header.
- Prowlarr `magnetUrl` and `downloadUrl` results are both accepted by the qBittorrent add flow.

## Phase 5: Bot Enhancements

Status: started with portable tests and Docker-era `/status`

Candidate features:

- Cleaner Telegram command UX.
- Search results with size, seeders, indexer, category, and source.
- Numbered result selection.
- qBittorrent queue commands.
- Pause, resume, delete, category, and save path controls.
- Better `/status` with stack health.
- Safer error messages that do not leak secrets.

Implementation notes:

- Windows test noise has been reduced: direct shell-script execution tests are skipped on Windows, while static script behavior checks still run.
- CPU usage tests now cover platforms without `os.getloadavg`, matching Windows behavior.
- `/status` now reports qBittorrent API health, Prowlarr reachability, Telegram API reachability, and container-safe disk/RAM/CPU information.
- `/status` no longer relies on host `systemctl` service checks as its primary health signal.
- Jackett appears in `/status` only when `JACKETT_API_KEY` is configured.
- The bot ensures qBittorrent category save paths for `Movie`, `TV`, and `Others` before adding torrents.
- qBittorrent completion hooks can delete completed torrent entries while keeping downloaded files.

## Phase 6: Operations

Goals:

- Make the stack pleasant to maintain on a headless Pi.
- Make migration to a new host straightforward.

Planned actions:

1. Add backup notes for `.env`, `data/`, and `downloads/`.
2. Add update instructions.
3. Add log inspection commands.
4. Add troubleshooting guide.
5. Decide whether Watchtower should update automatically or only notify.
