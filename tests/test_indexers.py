from unittest.mock import MagicMock

import bot.indexers as indexers


def test_select_indexer_provider_prefers_prowlarr(monkeypatch):
    monkeypatch.setenv("PROWLARR_API_KEY", "prowlarr-key")
    monkeypatch.setenv("JACKETT_API_KEY", "jackett-key")

    assert indexers.select_indexer_provider() == "prowlarr"


def test_select_indexer_provider_falls_back_to_jackett(monkeypatch):
    monkeypatch.delenv("PROWLARR_API_KEY", raising=False)
    monkeypatch.setenv("JACKETT_API_KEY", "jackett-key")

    assert indexers.select_indexer_provider() == "jackett"


def test_select_indexer_provider_falls_back_to_legacy_jackett_json(monkeypatch, tmp_path):
    legacy_path = tmp_path / "config.json"
    legacy_path.write_text('{"jackett_api_key": "legacy-key"}', encoding="utf-8")
    monkeypatch.delenv("PROWLARR_API_KEY", raising=False)
    monkeypatch.delenv("JACKETT_API_KEY", raising=False)
    monkeypatch.setenv("JACKETT_CONFIG_PATH", str(legacy_path))

    assert indexers.select_indexer_provider() == "jackett"


def test_search_prowlarr_uses_torznab_endpoint_and_normalizes_results(monkeypatch):
    monkeypatch.setenv("PROWLARR_URL", "http://prowlarr:9696")
    monkeypatch.setenv("PROWLARR_API_KEY", "secret-key")
    monkeypatch.setenv("PROWLARR_DEFAULT_INDEXER", "all")

    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss xmlns:torznab="http://torznab.com/schemas/2015/feed">
      <channel>
        <item>
          <title>Test Torrent</title>
          <link>magnet:?xt=urn:btih:test</link>
          <size>104857600</size>
          <torznab:attr name="seeders" value="42" />
          <torznab:attr name="tracker" value="Indexer One" />
        </item>
      </channel>
    </rss>
    """
    response = MagicMock(ok=True, text=xml)
    calls = []

    def fake_get(url, params, timeout):
        calls.append((url, params, timeout))
        return response

    monkeypatch.setattr(indexers.requests, "get", fake_get)

    results = indexers.search_prowlarr("ubuntu", max_results=5)

    assert calls == [
        (
            "http://prowlarr:9696/all/api",
            {"apikey": "secret-key", "t": "search", "q": "ubuntu"},
            8,
        )
    ]
    assert results == [
        {
            "title": "Test Torrent",
            "size": 100,
            "seeders": 42,
            "tracker": "Indexer One",
            "magnet": "magnet:?xt=urn:btih:test",
        }
    ]


def test_search_torrents_uses_jackett_fallback(monkeypatch):
    monkeypatch.delenv("PROWLARR_API_KEY", raising=False)
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
