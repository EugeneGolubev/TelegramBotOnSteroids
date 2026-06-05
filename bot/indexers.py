from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Literal

import requests

from bot import jackett
from bot.config import get_settings


IndexerProvider = Literal["prowlarr", "jackett", "none"]

TORZNAB_NAMESPACE = "{http://torznab.com/schemas/2015/feed}"


def select_indexer_provider() -> IndexerProvider:
    settings = get_settings()
    if settings.prowlarr_api_key:
        return "prowlarr"
    if settings.jackett_api_key or jackett.load_config().get("jackett_api_key"):
        return "jackett"
    return "none"


def search_torrents(query: str, max_results: int = 10) -> list[dict]:
    provider = select_indexer_provider()
    if provider == "prowlarr":
        return search_prowlarr(query, max_results=max_results)
    if provider == "jackett":
        return jackett.search_torrents(query, max_results=max_results)
    return []


def search_prowlarr(query: str, max_results: int = 10) -> list[dict]:
    settings = get_settings()
    prowlarr_url = settings.prowlarr_url.rstrip("/")
    api_key = settings.prowlarr_api_key
    if not prowlarr_url or not api_key:
        return []

    url = f"{prowlarr_url}/api/v1/search"
    params = {"query": query, "type": "search"}
    headers = {"X-Api-Key": api_key}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=8)
        if not response.ok:
            return []
        return normalize_prowlarr_results(response.json(), max_results=max_results)
    except Exception:
        return []


def normalize_prowlarr_results(items: list[dict], max_results: int = 10) -> list[dict]:
    results = []
    for item in items:
        download_url = item.get("magnetUrl") or item.get("downloadUrl")
        if not download_url:
            continue
        results.append(
            {
                "title": item.get("title", ""),
                "size": int(item.get("size") or 0) // (1024 * 1024),
                "seeders": int(item.get("seeders") or item.get("grabs") or 0),
                "tracker": item.get("indexer", ""),
                "magnet": download_url,
            }
        )
        if len(results) >= max_results:
            break
    return results


def normalize_torznab_results(xml_text: str, max_results: int = 10) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    results = []
    for item in root.findall(".//item"):
        magnet = _item_magnet(item)
        if not magnet:
            continue
        results.append(
            {
                "title": _item_text(item, "title"),
                "size": _item_int(item, "size") // (1024 * 1024),
                "seeders": _torznab_attr_int(item, "seeders"),
                "tracker": _first_torznab_attr(
                    item,
                    ("tracker", "indexer", "prowlarrindexer", "jackettindexer"),
                ),
                "magnet": magnet,
            }
        )
        if len(results) >= max_results:
            break
    return results


def _item_text(item: ET.Element, name: str) -> str:
    child = item.find(name)
    return (child.text or "") if child is not None else ""


def _item_int(item: ET.Element, name: str) -> int:
    try:
        return int(_item_text(item, name))
    except ValueError:
        return 0


def _item_magnet(item: ET.Element) -> str:
    link = _item_text(item, "link")
    if link.startswith("magnet:"):
        return link

    enclosure = item.find("enclosure")
    if enclosure is not None:
        url = enclosure.attrib.get("url", "")
        if url.startswith("magnet:"):
            return url

    return _first_torznab_attr(item, ("magneturl", "magnet"))


def _torznab_attr_int(item: ET.Element, name: str) -> int:
    try:
        return int(_first_torznab_attr(item, (name,)))
    except ValueError:
        return 0


def _first_torznab_attr(item: ET.Element, names: tuple[str, ...]) -> str:
    wanted = {name.lower() for name in names}
    for attr in item.findall(f"{TORZNAB_NAMESPACE}attr"):
        name = attr.attrib.get("name", "").lower()
        if name in wanted:
            return attr.attrib.get("value", "")
    return ""
