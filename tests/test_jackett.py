
from unittest.mock import MagicMock
import bot.jackett as jackett


def test_load_config_prefers_env(monkeypatch, tmp_path):
    legacy_path = tmp_path / "config.json"
    legacy_path.write_text(
        '{"jackett_url": "http://legacy:9117", "jackett_api_key": "legacy", "default_indexer": "legacy"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("JACKETT_CONFIG_PATH", str(legacy_path))
    monkeypatch.setenv("JACKETT_URL", "http://localhost:9117")
    monkeypatch.setenv("JACKETT_API_KEY", "abc123")
    monkeypatch.setenv("JACKETT_DEFAULT_INDEXER", "test")

    result = jackett.load_config()

    assert result["jackett_url"] == "http://localhost:9117"
    assert result["jackett_api_key"] == "abc123"
    assert result["default_indexer"] == "test"


def test_load_config_uses_legacy_json_for_missing_api_key(monkeypatch, tmp_path):
    legacy_path = tmp_path / "config.json"
    legacy_path.write_text(
        '{"jackett_url": "http://legacy:9117", "jackett_api_key": "legacy-key", "default_indexer": "legacy"}',
        encoding="utf-8",
    )
    monkeypatch.delenv("JACKETT_API_KEY", raising=False)
    monkeypatch.delenv("JACKETT_URL", raising=False)
    monkeypatch.delenv("JACKETT_DEFAULT_INDEXER", raising=False)
    monkeypatch.setenv("JACKETT_CONFIG_PATH", str(legacy_path))

    result = jackett.load_config()

    assert result["jackett_url"] == "http://legacy:9117"
    assert result["jackett_api_key"] == "legacy-key"
    assert result["default_indexer"] == "legacy"

def test_extract_magnet_from_link_redirect(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 302
    mock_resp.headers = {"Location": "magnet:?xt=urn:btih:example"}
    monkeypatch.setattr("requests.get", lambda *a, **kw: mock_resp)

    result = jackett.extract_magnet_from_link("http://dummy")
    assert result.startswith("magnet:")

def test_extract_magnet_from_link_fail(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    monkeypatch.setattr("requests.get", lambda *a, **kw: mock_resp)

    result = jackett.extract_magnet_from_link("http://dummy")
    assert result is None

def test_search_torrents_success(monkeypatch):
    fake_results = [{
        "Title": "Test Torrent",
        "Size": 104857600,
        "Seeders": 100,
        "Tracker": "tracker1",
        "MagnetUri": "magnet:?xt=urn:btih:test"
    }]
    mock_config = {
        "jackett_url": "http://localhost:9117",
        "jackett_api_key": "key",
        "default_indexer": "indexer"
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"Results": fake_results}
    mock_resp.status_code = 200

    monkeypatch.setattr(jackett, "load_config", lambda: mock_config)
    monkeypatch.setattr("requests.get", lambda *a, **kw: mock_resp)

    results = jackett.search_torrents("test")
    assert len(results) == 1
    assert results[0]["title"] == "Test Torrent"
