# Docker Architect Agent Brief

Mission:

- Convert the project into a portable multi-container Docker Compose stack.

Primary references:

- `docs/DOCKER_STACK_PLAN.md`
- `docs/CONFIGURATION_PLAN.md`

Constraints:

- Use several focused containers, not one monolithic image.
- Keep qBittorrent behind the VPN service.
- Keep Prowlarr as the preferred long-term indexer manager.
- Keep Jackett optional for compatibility.
- Keep the setup usable on Raspberry Pi Linux and Windows with Docker Desktop.

Expected outputs:

- `Dockerfile`
- `.dockerignore`
- `docker-compose.yml`
- optional Compose profile files only if clearly useful
- README updates with run commands

Validation ideas:

- `docker compose config`
- bot image build
- service startup smoke test where available
