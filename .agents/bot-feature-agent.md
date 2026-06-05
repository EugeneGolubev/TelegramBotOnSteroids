# Bot Feature Agent Brief

Mission:

- Improve Telegram bot behavior after the Docker foundation is in place.

Candidate features:

- Better `/status`.
- Search results with size, seeders, indexer, category, and source.
- Numbered result selection.
- Queue listing.
- Pause, resume, delete, category, and save path controls.
- Better error messages for unavailable services.

Constraints:

- Keep external APIs mocked in tests.
- Do not leak secrets.
- Preserve existing useful commands unless intentionally replaced.
- Prefer small, testable changes.

Expected outputs:

- focused handler changes
- integration helpers for qBittorrent and Prowlarr/Jackett
- tests for command behavior
