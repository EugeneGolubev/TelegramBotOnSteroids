
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bot.handlers import (
    _allowed,
    _format_speed,
    format_torrent_size,
    handle_message,
    handle_media_callback,
    handle_media_files,
    handle_status,
    handle_torrent_callback,
    handle_tstatus,
)
from bot.media import MediaEntry
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


@pytest.mark.parametrize("size_mb, expected", [
    (999, "999 MB"),
    (1000, "1 GB"),
    (1500, "1.5 GB"),
    (20000, "20 GB"),
])
def test_format_torrent_size(size_mb, expected):
    assert format_torrent_size(size_mb) == expected


@pytest.mark.parametrize("speed, expected", [
    (1024, "1.0 KB/s"),
    (1024**2, "1.0 MB/s"),
    (1024**3, "1.0 GB/s"),
])
def test_format_speed_uses_short_units(speed, expected):
    assert _format_speed(speed) == expected

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
    assert "█████████████░░░░░░░  1.5 MB/s" in text
    assert "⏳ Queued · 0.0%" in text
    assert "✅ Completed · 100.0%" in text
    assert "1 active · 1 queued · 1 completed" in text
    assert "```" not in text
    assert "| State" not in text
    assert long_name not in text
    assert "…" in text


@pytest.mark.asyncio
async def test_handle_tstatus_adds_reannounce_button_for_stalled_torrents(monkeypatch):
    update = MagicMock()
    update.effective_chat.type = "private"
    update.effective_chat.id = 123
    update.effective_user.id = 123
    update.message.reply_text = AsyncMock()

    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)
    monkeypatch.setattr("bot.handlers.qb_list_torrents", lambda: [
        {
            "name": "Stalled torrent",
            "hash": "a" * 40,
            "state": "stalledDL",
            "progress": 0,
        },
        {
            "name": "Downloading torrent",
            "hash": "b" * 40,
            "state": "downloading",
            "progress": 0.5,
        },
    ])

    await handle_tstatus(update, MagicMock())

    markup = update.message.reply_text.await_args.kwargs["reply_markup"]
    assert [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    ] == [f"torrent:reannounce:{'a' * 40}"]
    assert markup.inline_keyboard[0][0].text == "📣 Force Reannounce: Stalled torrent"


@pytest.mark.asyncio
async def test_handle_torrent_callback_requests_reannounce(monkeypatch):
    query = MagicMock()
    query.data = f"torrent:reannounce:{'a' * 40}"
    query.answer = AsyncMock()
    query.message.chat.type = "private"
    query.message.chat.id = 123
    query.from_user.id = 123
    update = MagicMock(callback_query=query)

    reannounce = MagicMock(return_value=True)
    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)
    monkeypatch.setattr("bot.handlers.qb_force_reannounce", reannounce)

    await handle_torrent_callback(update, MagicMock())

    reannounce.assert_called_once_with("a" * 40)
    assert query.answer.await_args_list[-1].args == ("✅ Reannounce requested.",)


@pytest.mark.asyncio
async def test_handle_torrent_callback_reports_reannounce_failure(monkeypatch):
    query = MagicMock()
    query.data = f"torrent:reannounce:{'a' * 40}"
    query.answer = AsyncMock()
    query.message.chat.type = "private"
    query.message.chat.id = 123
    query.from_user.id = 123
    update = MagicMock(callback_query=query)

    reannounce = MagicMock(return_value=False)
    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)
    monkeypatch.setattr("bot.handlers.qb_force_reannounce", reannounce)

    await handle_torrent_callback(update, MagicMock())

    reannounce.assert_called_once_with("a" * 40)
    assert query.answer.await_args_list[-1].args == ("❌ Could not force reannounce.",)
    assert query.answer.await_args_list[-1].kwargs == {"show_alert": True}


@pytest.mark.asyncio
async def test_handle_media_files_shows_category_picker(monkeypatch):
    update = MagicMock()
    update.effective_chat.type = "private"
    update.effective_chat.id = 123
    update.effective_user.id = 123
    update.message.reply_text = AsyncMock()

    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)

    await handle_media_files(update, MagicMock())

    markup = update.message.reply_text.await_args.kwargs["reply_markup"]
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    ]
    assert callbacks == [
        "media:category:Movie",
        "media:category:TV",
        "media:category:Others",
    ]


def _media_callback_update(data):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message.chat.type = "private"
    query.message.chat.id = 123
    query.from_user.id = 123

    update = MagicMock()
    update.callback_query = query
    return update, query


@pytest.mark.asyncio
async def test_media_category_callback_renders_cards(monkeypatch):
    update, query = _media_callback_update("media:category:TV")
    context = MagicMock()
    context.user_data = {}
    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)
    monkeypatch.setattr(
        "bot.handlers.list_media_entries",
        lambda category: [
            MediaEntry("Show.mkv", "Show.mkv", "file", 2048),
            MediaEntry("Series", "Series", "folder", 4096),
        ],
    )

    await handle_media_callback(update, context)

    text = query.edit_message_text.await_args.args[0]
    assert "Media files" in text
    assert "Show.mkv" in text
    assert "Type: File" in text
    assert "Type: Folder" in text
    assert "Size: 2.0 KiB" in text
    assert context.user_data["media_listing"]["category"] == "TV"


@pytest.mark.asyncio
async def test_media_page_callback_renders_next_page(monkeypatch):
    update, query = _media_callback_update("media:page:testtoken:1")
    context = MagicMock()
    context.user_data = {
        "media_listing": {
            "token": "testtoken",
            "category": "Movie",
            "entries": [
                MediaEntry(f"item-{index}.mkv", f"item-{index}.mkv", "file", index)
                for index in range(6)
            ],
            "page": 0,
        }
    }
    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)

    await handle_media_callback(update, context)

    text = query.edit_message_text.await_args.args[0]
    assert "Page 2/2" in text
    assert "item-5.mkv" in text
    assert "item-0.mkv" not in text


@pytest.mark.asyncio
async def test_media_select_shows_delete_and_cancel(monkeypatch):
    update, query = _media_callback_update("media:select:testtoken:0")
    context = MagicMock()
    context.user_data = {
        "media_listing": {
            "token": "testtoken",
            "category": "Movie",
            "entries": [MediaEntry("Series", "Series", "folder", 4096)],
            "page": 0,
        }
    }
    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)

    await handle_media_callback(update, context)

    text = query.edit_message_text.await_args.args[0]
    markup = query.edit_message_text.await_args.kwargs["reply_markup"]
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    ]
    assert "This will permanently delete the folder and all its contents." in text
    assert callbacks == ["media:delete:testtoken:0", "media:cancel:testtoken:0"]


@pytest.mark.asyncio
async def test_media_delete_refreshes_listing(monkeypatch):
    update, query = _media_callback_update("media:delete:testtoken:0")
    context = MagicMock()
    context.user_data = {
        "media_listing": {
            "token": "testtoken",
            "category": "Movie",
            "entries": [MediaEntry("Series", "Series", "folder", 4096)],
            "page": 0,
        }
    }
    deleted = MediaEntry("Series", "Series", "folder", 4096)
    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)
    delete_mock = MagicMock(return_value=deleted)
    monkeypatch.setattr("bot.handlers.delete_media_entry", delete_mock)
    monkeypatch.setattr("bot.handlers.list_media_entries", lambda category: [])

    await handle_media_callback(update, context)

    delete_mock.assert_called_once_with("Movie", "Series")
    text = query.edit_message_text.await_args.args[0]
    assert "Deleted folder: Series" in text
    assert "No files or folders found." in text


@pytest.mark.asyncio
async def test_media_expired_callback_does_not_delete(monkeypatch):
    update, query = _media_callback_update("media:delete:expired:0")
    context = MagicMock()
    context.user_data = {}
    monkeypatch.setattr("bot.handlers._allowed", lambda *a: True)
    delete_mock = MagicMock()
    monkeypatch.setattr("bot.handlers.delete_media_entry", delete_mock)

    await handle_media_callback(update, context)

    delete_mock.assert_not_called()
    assert "expired" in query.edit_message_text.await_args.args[0]
