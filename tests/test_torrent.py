
import pytest
from unittest.mock import patch, MagicMock
import bot.torrent as torrent

@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("QB_URL", "http://127.0.0.1:4545")
    monkeypatch.setenv("QB_USER", "admin")
    monkeypatch.setenv("QB_PASS", "adminadmin")

def test_add_torrent_valid_magnet(monkeypatch):
    mock_post = MagicMock(return_value=MagicMock(status_code=200))
    monkeypatch.setattr(torrent._session, "post", mock_post)
    monkeypatch.setattr(torrent, "_ensure_logged_in", lambda: True)

    result = torrent.add_torrent("magnet:?xt=urn:btih:example", "TV")
    assert result is True

def test_add_torrent_invalid_magnet():
    result = torrent.add_torrent("http://notamagnet", "TV")
    assert result is False

def test_qb_list_pending_torrents_filters_properly(monkeypatch):
    test_data = [
        {"state": "metaDL", "progress": 0.0, "added_on": 1, "name": "A"},
        {"state": "downloading", "progress": 0.5, "added_on": 2, "name": "B"},
        {"state": "stalledDL", "progress": 0.0, "added_on": 3, "name": "C"},
    ]
    monkeypatch.setattr(torrent, "qb_list_torrents", lambda: test_data)
    result = torrent.qb_list_pending_torrents(limit=None)
    assert len(result) == 2
    assert result[0]["name"] == "A"
    assert result[1]["name"] == "C"
