from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    """Raised when startup configuration is missing or invalid."""


@dataclass
class Settings:
    bot_token: str
    authorized_user_id: int | None
    allowed_chat_id: int | None
    plex_service_name: str
    downloads_path: str

    qb_url: str
    qb_user: str
    qb_pass: str
    qb_category_paths: dict[str, str]

    prowlarr_url: str
    prowlarr_api_key: str
    prowlarr_default_indexer: str

    jackett_url: str
    jackett_api_key: str
    jackett_default_indexer: str
    jackett_config_path: str


def load_root_dotenv(project_root: str | Path | None = None) -> bool:
    """Load the repo-root .env file without overriding runtime env vars."""
    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    return load_dotenv(dotenv_path=root / ".env", override=False)


def _optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def get_settings() -> Settings:
    """Load settings from root .env and environment every call.

    Keeping this simple (no caching) helps tests that monkeypatch env.
    """
    load_root_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "")
    authorized_user_id = _optional_int("AUTHORIZED_USER_ID")
    allowed_chat_id = _optional_int("ALLOWED_CHAT_ID")

    plex_service_name = os.getenv("PLEX_SERVICE_NAME", "plexmediaserver")
    downloads_path = os.getenv("DOWNLOADS_PATH", "/downloads")

    qb_url = os.getenv("QB_URL", "http://vpn:8080").rstrip("/")
    qb_user = os.getenv("QB_USER", "")
    qb_pass = os.getenv("QB_PASS", "")
    qb_category_paths = {
        "Movie": os.getenv("QB_CATEGORY_MOVIE_PATH", f"{downloads_path.rstrip('/')}/Movie"),
        "TV": os.getenv("QB_CATEGORY_TV_PATH", f"{downloads_path.rstrip('/')}/TV"),
        "Others": os.getenv("QB_CATEGORY_OTHERS_PATH", f"{downloads_path.rstrip('/')}/Others"),
    }

    prowlarr_url = os.getenv("PROWLARR_URL", "http://prowlarr:9696").rstrip("/")
    prowlarr_api_key = os.getenv("PROWLARR_API_KEY", "")
    prowlarr_default_indexer = os.getenv("PROWLARR_DEFAULT_INDEXER", "all")

    jackett_url = os.getenv("JACKETT_URL", "http://jackett:9117").rstrip("/")
    jackett_api_key = os.getenv("JACKETT_API_KEY", "")
    jackett_default_indexer = os.getenv("JACKETT_DEFAULT_INDEXER", "all")
    jackett_config_path = os.getenv("JACKETT_CONFIG_PATH", "config.sample.json")

    return Settings(
        bot_token=bot_token,
        authorized_user_id=authorized_user_id,
        allowed_chat_id=allowed_chat_id,
        plex_service_name=plex_service_name,
        downloads_path=downloads_path,
        qb_url=qb_url,
        qb_user=qb_user,
        qb_pass=qb_pass,
        qb_category_paths=qb_category_paths,
        prowlarr_url=prowlarr_url,
        prowlarr_api_key=prowlarr_api_key,
        prowlarr_default_indexer=prowlarr_default_indexer,
        jackett_url=jackett_url,
        jackett_api_key=jackett_api_key,
        jackett_default_indexer=jackett_default_indexer,
        jackett_config_path=jackett_config_path,
    )


def validate_settings(settings: Settings) -> None:
    """Validate required bot startup settings without exposing values."""
    missing = []
    invalid = []

    if not settings.bot_token:
        missing.append("BOT_TOKEN")
    if settings.authorized_user_id is None:
        raw_value = os.getenv("AUTHORIZED_USER_ID", "")
        (invalid if raw_value else missing).append("AUTHORIZED_USER_ID")
    if settings.allowed_chat_id is None:
        raw_value = os.getenv("ALLOWED_CHAT_ID", "")
        (invalid if raw_value else missing).append("ALLOWED_CHAT_ID")
    if not settings.qb_user:
        missing.append("QB_USER")
    if not settings.qb_pass:
        missing.append("QB_PASS")
    if not settings.prowlarr_api_key and not settings.jackett_api_key:
        missing.append("PROWLARR_API_KEY or JACKETT_API_KEY")

    parts = []
    if missing:
        parts.append(f"missing required keys: {', '.join(sorted(missing))}")
    if invalid:
        parts.append(f"invalid integer keys: {', '.join(sorted(invalid))}")

    if parts:
        raise ConfigError("Configuration error: " + "; ".join(parts))

