from unittest.mock import MagicMock

import bot.indexers as indexers


def test_select_indexer_provider_prefers_prowlarr(monkeypatch):
    monkeypatch.setenv("PROWLARR_API_KEY", "prowlarr-key")
    monkeypatch.setenv("JACKETT_API_KEY", "jackett-key")

    assert indexers.select_indexer_provider() == "prowlarr"


def test_select_indexer_provider_falls_back_to_jackett(monkeypatch):
    monkeypatch.setenv("PROWLARR_API_KEY", "")
    monkeypatch.setenv("JACKETT_API_KEY", "jackett-key")

    assert indexers.select_indexer_provider() == "jackett"


def test_select_indexer_provider_falls_back_to_legacy_jackett_json(monkeypatch):
    monkeypatch.setenv("PROWLARR_API_KEY", "")
    monkeypatch.setenv("JACKETT_API_KEY", "")
    monkeypatch.setattr(indexers.jackett, "load_config", lambda: {"jackett_api_key": "legacy-key"})

    assert indexers.select_indexer_provider() == "jackett"


def test_search_prowlarr_uses_api_search_and_normalizes_results(monkeypatch):
    monkeypatch.setenv("PROWLARR_URL", "http://prowlarr:9696")
    monkeypatch.setenv("PROWLARR_API_KEY", "secret-key")
    monkeypatch.setenv("PROWLARR_DEFAULT_INDEXER", "all")

    payload = [
        {
            "title": "Test Torrent",
            "downloadUrl": "http://prowlarr:9696/1/download?apikey=redacted",
            "size": 104857600,
            "seeders": 42,
            "indexer": "Indexer One",
        }
    ]
    response = MagicMock(ok=True)
    response.json.return_value = payload
    calls = []

    def fake_get(url, headers, params, timeout):
        calls.append((url, params, timeout))
        return response

    monkeypatch.setattr(indexers.requests, "get", fake_get)

    results = indexers.search_prowlarr("ubuntu", max_results=5)

    assert calls == [
        (
            "http://prowlarr:9696/api/v1/search",
            {"query": "ubuntu", "type": "search"},
            8,
        )
    ]
    assert results == [
        {
            "title": "Test Torrent",
            "size": 100,
            "seeders": 42,
            "tracker": "Indexer One",
            "magnet": "http://prowlarr:9696/1/download?apikey=redacted",
        }
    ]


def test_search_torrents_uses_jackett_fallback(monkeypatch):
    monkeypatch.setenv("PROWLARR_API_KEY", "")
    monkeypatch.setenv("JACKETT_API_KEY", "jackett-key")
    monkeypatch.setattr(indexers.jackett, "search_torrents", lambda q, max_results=10: [{"title": q}])

    assert indexers.search_torrents("fallback") == [{"title": "fallback"}]


def test_search_torrents_returns_empty_for_failed_prowlarr_response(monkeypatch):
    monkeypatch.setenv("PROWLARR_API_KEY", "prowlarr-key")
    response = MagicMock(ok=False, text="")
    monkeypatch.setattr(indexers.requests, "get", lambda *a, **kw: response)

    assert indexers.search_torrents("anything") == []


def test_search_torrents_returns_empty_for_malformed_prowlarr_response(monkeypatch):
    monkeypatch.setenv("PROWLARR_API_KEY", "prowlarr-key")
    response = MagicMock(ok=True, text="<not xml")
    monkeypatch.setattr(indexers.requests, "get", lambda *a, **kw: response)

    assert indexers.search_torrents("anything") == []
