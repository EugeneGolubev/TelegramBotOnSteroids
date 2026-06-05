import requests

from bot.config import get_settings

_session = requests.Session()


def _ensure_logged_in() -> bool:
    """
    Login only if there is no SID cookie or last login likely expired.
    """
    settings = get_settings()
    try:
        # If we already have a SID cookie, assume we are logged in
        if "SID" in _session.cookies.get_dict():
            return True
        r = _session.post(
            f"{settings.qb_url}/api/v2/auth/login",
            data={"username": settings.qb_user, "password": settings.qb_pass},
            timeout=5,
        )
        if r.status_code not in (200, 204):
            return False
        if "SID" in _session.cookies.get_dict():
            return True
        api_check = _session.get(f"{settings.qb_url}/api/v2/app/version", timeout=5)
        return api_check.ok
    except Exception:
        return False


def _ensure_category_path(category: str | None) -> bool:
    if not category:
        return True

    settings = get_settings()
    save_path = settings.qb_category_paths.get(category)
    if not save_path:
        return True

    data = {"category": category, "savePath": save_path}
    try:
        create = _session.post(
            f"{settings.qb_url}/api/v2/torrents/createCategory",
            data=data,
            timeout=5,
        )
        if create.status_code not in (200, 204, 409):
            return False
        edit = _session.post(
            f"{settings.qb_url}/api/v2/torrents/editCategory",
            data=data,
            timeout=5,
        )
        return edit.status_code in (200, 204)
    except Exception:
        return False


def add_torrent(magnet: str, category: str | None = None) -> bool:
    """
    Add a magnet or torrent download URL to qBittorrent, optional category.
    """
    if not magnet or not magnet.startswith(("magnet:", "http://", "https://")):
        return False
    if not _ensure_logged_in():
        return False
    if not _ensure_category_path(category):
        return False
    data = {"urls": magnet}
    if category:
        data["category"] = category
    settings = get_settings()
    try:
        _session.post(f"{settings.qb_url}/api/v2/torrents/add", data=data, timeout=5)
        return True
    except Exception:
        return False

def qb_list_torrents() -> list[dict]:
    """
    Return list of torrents with their states.
    """
    if not _ensure_logged_in():
        return []
    settings = get_settings()
    try:
        r = _session.get(f"{settings.qb_url}/api/v2/torrents/info", timeout=5)
        return r.json() if r.ok else []
    except Exception:
        return []

def qb_health() -> bool:
    """
    Lightweight check that auth + API works.
    """
    if not _ensure_logged_in():
        return False
    settings = get_settings()
    try:
        r = _session.get(f"{settings.qb_url}/api/v2/app/version", timeout=5)
        return r.ok
    except Exception:
        return False

# --- NEW: pending/not-started helper ---
PENDING_STATES = {
    "metaDL",
    "forcedMetaDL",
    "queuedDL",
    "stalledDL",
    "checkingDL",
    "allocating",
}

def qb_list_pending_torrents(limit: int | None = 10, count_only: bool = False):
    """
    Returns a list of torrents that haven't really started downloading yet:
      - state in PENDING_STATES (metadata/queued/stalled/etc.)
      - OR progress == 0.0
    If count_only=True, returns total count (int) instead of a list.
    """
    try:
        all_ts = qb_list_torrents()
    except Exception:
        return 0 if count_only else []
    pending = [
        t for t in all_ts
        if (t.get("state") in PENDING_STATES) or (float(t.get("progress", 0)) == 0.0)
    ]
    # stable sort by added_on then name
    pending.sort(key=lambda t: (t.get("added_on", 0) or 0, t.get("name", "") or ""))
    if count_only:
        return len(pending)
    if limit is None:
        return pending
    return pending[:limit]
