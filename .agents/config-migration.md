# Config Migration Agent Brief

Mission:

- Move the project toward one root `.env` configuration source.

Primary references:

- `docs/CONFIGURATION_PLAN.md`
- `.env.example`

Constraints:

- Never commit real secrets.
- Keep `.env.example` complete but safe.
- Avoid hardcoded Pi paths.
- Avoid depending on `/opt/telegrambot/config.json`.
- Do not print secret values in logs or exceptions.

Expected outputs:

- updated config loading in `bot/`
- updated scripts in `scripts/`
- tests for missing and optional config
- README updates

Validation ideas:

- unit tests for config parsing
- syntax check
- local run with placeholder-safe validation behavior
