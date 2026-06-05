import os
from pathlib import Path

import pytest

import bot.config as config
from bot.config import (
    ConfigError,
    get_settings,
    load_root_dotenv,
    validate_settings,
)


CONFIG_ENV_KEYS = (
    "BOT_TOKEN",
    "AUTHORIZED_USER_ID",
    "ALLOWED_CHAT_ID",
    "QB_URL",
    "QB_USER",
    "QB_PASS",
    "QB_CATEGORY_MOVIE_PATH",
    "QB_CATEGORY_TV_PATH",
    "QB_CATEGORY_OTHERS_PATH",
    "PROWLARR_URL",
    "PROWLARR_API_KEY",
    "PROWLARR_DEFAULT_INDEXER",
    "JACKETT_URL",
    "JACKETT_API_KEY",
    "JACKETT_DEFAULT_INDEXER",
    "JACKETT_CONFIG_PATH",
)


def clear_config_env():
    for key in CONFIG_ENV_KEYS:
        os.environ.pop(key, None)


@pytest.fixture(autouse=True)
def isolated_config_env(monkeypatch, tmp_path):
    clear_config_env()
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    yield
    clear_config_env()


def test_load_root_dotenv_loads_repo_env_without_overriding_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BOT_TOKEN=from-file\n"
        "AUTHORIZED_USER_ID=123\n"
        "ALLOWED_CHAT_ID=-456\n"
        "QB_USER=file-user\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BOT_TOKEN", "from-env")
    monkeypatch.delenv("QB_USER", raising=False)

    assert load_root_dotenv(tmp_path) is True

    assert get_settings().bot_token == "from-env"
    assert get_settings().qb_user == "file-user"


def test_validate_settings_reports_missing_keys_without_secret_values(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "super-secret-token")

    with pytest.raises(ConfigError) as exc_info:
        validate_settings(get_settings())

    message = str(exc_info.value)
    assert "AUTHORIZED_USER_ID" in message
    assert "ALLOWED_CHAT_ID" in message
    assert "BOT_TOKEN" not in message
    assert "super-secret-token" not in message


def test_validate_settings_reports_invalid_integer_keys(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "dummy")
    monkeypatch.setenv("AUTHORIZED_USER_ID", "not-an-int")
    monkeypatch.setenv("ALLOWED_CHAT_ID", "-100")

    with pytest.raises(ConfigError, match="AUTHORIZED_USER_ID"):
        validate_settings(get_settings())


def test_get_settings_uses_portable_defaults():
    settings = get_settings()

    assert settings.qb_url == "http://vpn:8080"
    assert settings.downloads_path == "/downloads"
    assert settings.qb_category_paths == {
        "Movie": "/downloads/Movie",
        "TV": "/downloads/TV",
        "Others": "/downloads/Others",
    }
    assert settings.prowlarr_url == "http://prowlarr:9696"
    assert settings.prowlarr_default_indexer == "all"
    assert settings.jackett_url == "http://jackett:9117"
    assert settings.jackett_default_indexer == "all"
    assert settings.jackett_config_path == str(Path("config.sample.json"))
