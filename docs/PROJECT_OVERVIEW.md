# TelegramBotOnSteroids Project Overview

## Background

This project started as a Raspberry Pi 5 Telegram torrent bot. The old version runs on a headless Linux Pi and talks to supporting tools installed directly on the host, such as qBittorrent.

The new version should preserve the useful behavior of the old bot while making the whole setup easier to move, rebuild, update, and test.

## Target Outcome

Create a portable Docker Compose based media automation stack that can run on:

- Raspberry Pi Linux, headless
- Other Linux hosts
- Windows with Docker Desktop
- macOS with Docker Desktop, if needed later

The stack should be easy to move to another host by copying the project folder, providing a `.env` file, and running Docker Compose.

## Main Services

- `telegram-bot`: custom Python Telegram bot.
- `vpn`: VPN network gateway used by torrent traffic.
- `qbittorrent`: torrent client, routed through the VPN service.
- `prowlarr`: indexer manager used by the bot.
- `watchtower`: optional automatic container updater.

## Guiding Decisions

- Use several focused containers managed by one Docker Compose project.
- Do not build one large all-in-one container.
- Use one root `.env` file for secrets and environment-specific values.
- Keep `.env` out of git and commit `.env.example`.
- Keep persistent service config under ignored local folders such as `data/`.
- Keep downloads under a mounted folder such as `downloads/`.
- Avoid Raspberry Pi specific hardcoded paths.
- Keep Windows development/testing possible.

## Migration Strategy

Start by containerizing the current working bot and support stack with minimal behavior changes. After the stack is portable, improve the bot features and user experience in smaller, safer steps.

## Current Docker State

The repository includes a Docker Compose stack. The default services are `telegram-bot`, `vpn`, `qbittorrent`, and `prowlarr`; the optional `updates` profile adds `watchtower`.

qBittorrent is routed through the VPN service with `network_mode: service:vpn`, and its Web UI is exposed through the VPN service port mapping. The bot checks Gluetun's internal, read-only control API for VPN state; that API is intentionally not published on the host.
