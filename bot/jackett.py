import os
import requests
import json
from pathlib import Path

from bot.config import PROJECT_ROOT, get_settings


def load_config() -> dict:
    """Load Jackett config from env, with JSON as a migration fallback.

    Supports env keys: JACKETT_URL, JACKETT_API_KEY, JACKETT_DEFAULT_INDEXER.
    """
    settings = get_settings()
    config_path = Path(settings.jackett_config_path)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    try:
        with config_path.open(encoding="utf-8") as f:
            legacy_cfg = json.load(f)
    except Exception:
        legacy_cfg = {}

    return {
        "jackett_url": (
            settings.jackett_url
            if "JACKETT_URL" in os.environ
            else legacy_cfg.get("jackett_url", settings.jackett_url)
        ),
        "jackett_api_key": (
            settings.jackett_api_key
            if "JACKETT_API_KEY" in os.environ
            else legacy_cfg.get("jackett_api_key", settings.jackett_api_key)
        ),
        "default_indexer": (
            settings.jackett_default_indexer
            if "JACKETT_DEFAULT_INDEXER" in os.environ
            else legacy_cfg.get("default_indexer", settings.jackett_default_indexer)
        ),
    }


def extract_magnet_from_link(link: str) -> str | None:
    try:
        res = requests.get(link, allow_redirects=False, timeout=5)
        if res.status_code in (301, 302):
            loc = res.headers.get("Location", "")
            if loc.startswith("magnet:"):
                return loc
    except Exception:
        pass
    return None

def search_torrents(query: str, max_results: int = 10) -> list[dict]:
    cfg = load_config()
    idx = cfg.get('default_indexer', '')
    jackett_url = (cfg.get('jackett_url', '') or '').rstrip('/')
    api_key = cfg.get('jackett_api_key', '')
    if not jackett_url or not api_key or not idx:
        return []
    url = f"{jackett_url}/api/v2.0/indexers/{idx}/results"
    params = {"apikey": api_key, "Query": query}
    try:
        resp = requests.get(url, params=params, timeout=8)
        items = resp.json().get("Results", [])
    except Exception:
        return []
    results = []
    for item in items:
        magnet = item.get("MagnetUri") or extract_magnet_from_link(item.get("Link", ""))
        if not magnet:
            continue
        results.append({
            "title": item.get("Title", ""),
            "size": item.get("Size", 0) // (1024 * 1024),
            "seeders": item.get("Seeders", 0),
            "tracker": item.get("Tracker", ""),
            "magnet": magnet
        })
        if len(results) >= max_results:
            break
    return results
