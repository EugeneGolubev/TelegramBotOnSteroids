# Repository Guidelines

## Project Direction
- The old bot currently runs on a Raspberry Pi 5 with host-installed support tools.
- The new version should be portable across Raspberry Pi Linux, regular Linux, Windows with Docker Desktop, and macOS where possible.
- Runtime packaging should use one Docker Compose project with several focused containers, not one monolithic container.
- The target stack is: `telegram-bot`, `vpn`, `qbittorrent`, `prowlarr`, optional `jackett`, and `watchtower`.
- Keep the project movable to another host by storing all persistent data under repo-local ignored folders such as `data/` and `downloads/`.

## Project Structure & Module Organization
- `bot/`: Telegram bot code (`main.py`, `handlers.py`, `jackett.py`, `torrent.py`, `utils.py`).
- `tests/`: Pytest suite covering handlers, indexer integration, torrent integration, and utilities.
- `scripts/`: Shell helpers currently intended for qBittorrent post-download hooks.
- `docs/`: Planning and architecture documents for the new Docker-based version.
- `.agents/`: Optional agent/task briefs for future coding sessions.
- `requirements.txt`, `run_all_tests.sh`: Python deps and test runner.

## Build, Test, and Development Commands
- Create venv: `python3 -m venv mybotenv && source mybotenv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Run bot locally: `python -m bot.main`
- Run tests + coverage: `./run_all_tests.sh` or `PYTHONPATH=. pytest --cov=bot --cov-report=term --cov-report=html tests/`
- Future Docker run target: `docker compose up -d`

## Coding Style & Naming Conventions
- Python, PEP 8, 4-space indent; prefer f-strings and `logging`.
- Use snake_case for files, functions, and variables; PascalCase for classes.
- Type hints where practical, especially public functions and new modules.
- Keep diffs scoped. Avoid unrelated rewrites while the container migration is in progress.

## Testing Guidelines
- Framework: Pytest.
- Name tests `tests/test_*.py`; keep unit tests hermetic by mocking network, filesystem, and process calls.
- Add or update tests for changed behavior.
- During Docker work, prefer tests that can run without live Telegram, qBittorrent, Prowlarr, Jackett, or VPN services.

## Configuration & Secrets
- Use one root `.env` file for environment-specific settings and secrets.
- Commit `.env.example`, never commit real `.env` files.
- Prefer environment variables over hardcoded paths or host-specific config files.
- Avoid hardcoded Raspberry Pi paths such as `/opt/telegrambot`.
- Do not print secrets in logs, error messages, or test output.

## Docker Design Rules
- Use separate containers for separate responsibilities.
- Route qBittorrent through the VPN container.
- Keep Telegram bot, Prowlarr, and Watchtower on normal service networking unless a specific need says otherwise.
- Prowlarr is the preferred long-term indexer manager.
- Jackett may remain as an optional compatibility service while the bot is migrated.
- Do not rely on `systemctl` from inside containers.

## Commit & Pull Request Guidelines
- Commit messages: imperative mood, concise subject, optional body explaining why.
- Prefer Conventional Commits where natural: `feat:`, `fix:`, `chore:`, `test:`, `docs:`.
- PRs should include summary, test evidence, and config changes.
