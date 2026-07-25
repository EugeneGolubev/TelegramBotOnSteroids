"""Read-only access to the Gluetun control server."""

from __future__ import annotations

from typing import Any

import requests

from bot.config import get_settings


def _get_control_data(path: str) -> dict[str, Any] | None:
    """Return JSON from Gluetun's read-only control API, if available."""
    settings = get_settings()
    try:
        response = requests.get(f"{settings.vpn_control_url}{path}", timeout=3)
        if not response.ok:
            return None
        data = response.json()
        return data if isinstance(data, dict) else None
    except (requests.RequestException, ValueError):
        return None


def get_vpn_info() -> dict[str, str | int | None]:
    """Get the connection state, public IP, and forwarded port from Gluetun."""
    status_data = _get_control_data("/v1/vpn/status") or {}
    ip_data = _get_control_data("/v1/publicip/ip") or {}
    port_data = _get_control_data("/v1/portforward") or {}

    port = port_data.get("port")
    if not isinstance(port, int) or port <= 0:
        port = None

    status = status_data.get("status")
    public_ip = ip_data.get("public_ip")
    return {
        "status": status if isinstance(status, str) else None,
        "public_ip": public_ip if isinstance(public_ip, str) else None,
        "forwarded_port": port,
    }
