from unittest.mock import MagicMock

import bot.vpn as vpn


def test_get_vpn_info_reads_control_endpoints(monkeypatch):
    responses = iter([
        {"status": "running"},
        {"public_ip": "203.0.113.10"},
        {"port": 45678},
    ])

    def fake_get(url, timeout):
        response = MagicMock(ok=True)
        response.json.return_value = next(responses)
        return response

    monkeypatch.setattr(vpn.requests, "get", fake_get)

    assert vpn.get_vpn_info() == {
        "status": "running",
        "public_ip": "203.0.113.10",
        "forwarded_port": 45678,
    }


def test_get_vpn_info_handles_unavailable_control_server(monkeypatch):
    monkeypatch.setattr(vpn, "_get_control_data", lambda path: None)

    assert vpn.get_vpn_info() == {
        "status": None,
        "public_ip": None,
        "forwarded_port": None,
    }
