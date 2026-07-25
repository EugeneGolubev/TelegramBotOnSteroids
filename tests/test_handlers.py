
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.handlers import _allowed, handle_message, handle_status, handle_tstatus
import types

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("AUTHORIZED_USER_ID", "123")
    monkeypatch.setenv("ALLOWED_CHAT_ID", "-100123")
    monkeypatch.setenv("BOT_TOKEN", "dummy")

@pytest.mark.asyncio
@pytest.mark.parametrize("chat_type,chat_id,user_id,expected", [
    ("private", 123, 123, True),
    ("group", -100123, 555, True),
    ("supergroup", -100123, 555, True),
    ("group", -100999, 555, False),
    ("private", 999, 999, False),
    ("channel", -1, 1, False),
])
async def test__allowed_behavior(monkeypatch, chat_type, chat_id, user_id, expected):
    assert _allowed(chat_type, chat_id, user_id) == expected

@pytest.mark.asyncio
async def test_handle_message_search(monkeypatch):
    mock_update = MagicMock()
    mock_update.effective_chat.type = "private"
    mock_update.effective_chat.id = 123
    mock_update.effective_user.id = 123
    mock_update.message.text = "test torrent"
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.user_data = {}

    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)
    monkeypatch.setattr("bot.handlers.search_torrents", lambda q: [
        {
            "title": f"Torrent {i}",
            "size": 123,
            "seeders": 50,
            "tracker": "X",
            "magnet": "magnet:?xt=urn"
        } for i in range(3)
    ])
    monkeypatch.setattr("bot.handlers.search_torrents", lambda q: [{
        "title": "Test",
        "size": 123,
        "seeders": 50,
        "tracker": "X",
        "magnet": "magnet:?xt=urn"
    }] * 3)
    monkeypatch.setattr("bot.handlers.send_search_page", AsyncMock())

    await handle_message(mock_update, mock_context)
    assert mock_context.user_data["search_page"] == 0
    assert len(mock_context.user_data["search_results"]) == 3

@pytest.mark.asyncio
async def test_handle_status(monkeypatch):
    update = MagicMock()
    update.effective_chat.type = "private"
    update.effective_chat.id = 123
    update.effective_user.id = 123
    update.message.reply_text = AsyncMock()

    context = MagicMock()

    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)
    monkeypatch.setattr("bot.handlers.qb_health", lambda: True)
    monkeypatch.setattr("bot.handlers.qb_list_torrents", lambda: [{"state": "downloading", "progress": 0.5}])
    monkeypatch.setattr("bot.handlers.qb_list_pending_torrents", lambda limit=None, count_only=True: 1)
    monkeypatch.setattr("bot.handlers.check_url_status", lambda u: "✅ Online")
    monkeypatch.setattr("bot.handlers.check_service", lambda s: "✅ Running")
    monkeypatch.setattr("bot.handlers.check_telegram_api", lambda token: "✅ Online")
    monkeypatch.setattr("bot.handlers.get_disk_space", lambda: "42 GB free")
    monkeypatch.setattr("bot.handlers.get_ram_usage", lambda: "1024 MB / 4096 MB")
    monkeypatch.setattr("bot.handlers.get_cpu_usage", lambda: "20.0% (Load: 0.5, 0.2)")
    monkeypatch.setattr("bot.handlers.get_vpn_info", lambda: {
        "status": "running", "public_ip": "203.0.113.10", "forwarded_port": 45678,
    })
    monkeypatch.setattr("bot.handlers.qb_get_preferences", lambda: {
        "listen_port": 45678, "current_network_interface": "tun0",
    })

    await handle_status(update, context)
    text = update.message.reply_text.await_args.args[0]
    assert "*📊 System Status*" in text
    assert "*Services*" in text
    assert "*Downloads*" in text
    assert "*🔒 VPN Routing*" in text
    assert "```" not in text
    assert "• qBittorrent — ✅ Online" in text
    assert "↪️ Port forwarding: ✅ 45678" in text

@pytest.mark.asyncio
async def test_handle_status_reports_compose_api_health_without_systemctl(monkeypatch):
    update = MagicMock()
    update.effective_chat.type = "private"
    update.effective_chat.id = 123
    update.effective_user.id = 123
    update.message.reply_text = AsyncMock()

    context = MagicMock()

    monkeypatch.setenv("PROWLARR_API_KEY", "prowlarr-key")
    monkeypatch.delenv("JACKETT_API_KEY", raising=False)
    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)
    monkeypatch.setattr("bot.handlers.qb_health", lambda: True)
    monkeypatch.setattr("bot.handlers.qb_list_torrents", lambda: [{"state": "downloading", "progress": 0.5}])
    monkeypatch.setattr("bot.handlers.qb_list_pending_torrents", lambda limit=None, count_only=True: 1)
    monkeypatch.setattr(
        "bot.handlers.check_url_status",
        lambda url: "ONLINE" if "prowlarr" in url else "UNEXPECTED",
    )
    monkeypatch.setattr("bot.handlers.check_service", lambda s: (_ for _ in ()).throw(AssertionError(s)))
    monkeypatch.setattr("bot.handlers.check_telegram_api", lambda token: "TELEGRAM_OK")
    monkeypatch.setattr("bot.handlers.get_disk_space", lambda: "42 GB free")
    monkeypatch.setattr("bot.handlers.get_ram_usage", lambda: "1024 MB / 4096 MB")
    monkeypatch.setattr("bot.handlers.get_cpu_usage", lambda: "20.0%")
    monkeypatch.setattr("bot.handlers.get_vpn_info", lambda: {
        "status": None, "public_ip": None, "forwarded_port": None,
    })
    monkeypatch.setattr("bot.handlers.qb_get_preferences", lambda: {})

    await handle_status(update, context)

    text = update.message.reply_text.await_args.args[0]
    assert "qBittorrent" in text
    assert "• qBittorrent — ✅ Online" in text
    assert "Prowlarr" in text
    assert "ONLINE" in text
    assert "Jackett" not in text
    assert "Telegram Bot" in text
    assert "TELEGRAM_OK" in text


@pytest.mark.asyncio
async def test_handle_tstatus_renders_mobile_friendly_torrent_cards(monkeypatch):
    update = MagicMock()
    update.effective_chat.type = "private"
    update.effective_chat.id = 123
    update.effective_user.id = 123
    update.message.reply_text = AsyncMock()

    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)
    long_name = "A very long torrent name that should be shortened before it overwhelms the mobile card display"
    monkeypatch.setattr("bot.handlers.qb_list_torrents", lambda: [
        {
            "name": long_name, "state": "downloading", "progress": 0.625,
            "dlspeed": 1_572_864,
        },
        {"name": "Waiting torrent", "state": "queuedDL", "progress": 0},
        {"name": "Finished torrent", "state": "uploading", "progress": 1},
    ])

    await handle_tstatus(update, MagicMock())

    text = update.message.reply_text.await_args.args[0]
    assert text.startswith("📋 Torrent Status\n\n")
    assert "⬇️ Downloading · 62.5%" in text
    assert "█████████████░░░░░░░  1.5 MiB/s" in text
    assert "⏳ Queued · 0.0%" in text
    assert "✅ Completed · 100.0%" in text
    assert "1 active · 1 queued · 1 completed" in text
    assert "```" not in text
    assert "| State" not in text
    assert long_name not in text
    assert "…" in text
