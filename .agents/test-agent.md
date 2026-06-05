# Test Agent Brief

Mission:

- Keep the project testable across Windows, Linux, and Raspberry Pi.

Primary goals:

- Make tests hermetic.
- Mock Telegram, qBittorrent, Prowlarr, Jackett, VPN, and filesystem side effects where possible.
- Keep tests runnable without Docker when practical.
- Add Docker validation commands for infrastructure changes.

Expected outputs:

- focused pytest tests
- fixtures for config and service clients
- documentation for test commands

Validation commands:

```bash
PYTHONPATH=. pytest tests/
python -m compileall bot tests
docker compose config
```
