# TelegramBotOnSteroids Project Overview

## Background

This project started as a Raspberry Pi 5 Telegram torrent bot. The old version runs on a headless Linux Pi and talks to supporting tools that are installed directly on the host, such as qBittorrent and Jackett.

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
- `prowlarr`: preferred long-term indexer manager.
- `jackett`: optional compatibility service for the old bot integration.
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

The repository now includes an initial Docker Compose stack. The default services are `telegram-bot`, `vpn`, `qbittorrent`, and `prowlarr`. Optional profiles add `jackett` for legacy compatibility and `watchtower` for updates.

qBittorrent is routed through the VPN service with `network_mode: service:vpn`, and its Web UI is exposed through the VPN service port mapping.
