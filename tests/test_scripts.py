
import subprocess
import os
import tempfile
from pathlib import Path
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRECT_SHELL_ON_WINDOWS = pytest.mark.skipif(
    os.name == "nt",
    reason="Windows does not execute .sh files directly without an explicit shell",
)

def write_script(name, content):
    path = Path(tempfile.gettempdir()) / name
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)
    return str(path)

@SKIP_DIRECT_SHELL_ON_WINDOWS
def test_notify_complete_sh(monkeypatch):
    env_path = Path(tempfile.gettempdir()) / "test_env_notify.env"
    env_path.write_text("BOT_TOKEN=dummy\nALLOWED_CHAT_ID=123456", encoding="utf-8")

    script = write_script("notify_complete.sh", """#!/bin/bash
BOT_TOKEN="dummy"
CHAT_ID="123456"
TORRENT_NAME="TestTorrent"
echo "Would notify $CHAT_ID with $TORRENT_NAME"
exit 0
""")
    result = subprocess.run([script], capture_output=True, text=True)
    assert "Would notify 123456 with TestTorrent" in result.stdout

    os.remove(script)
    env_path.unlink(missing_ok=True)

@SKIP_DIRECT_SHELL_ON_WINDOWS
def test_delete_completed_sh_logic(monkeypatch):
    script = write_script("delete_completed.sh", """#!/bin/bash
echo "Authenticating to qBittorrent..."
echo "Checking for completed torrents..."
echo "Deleting torrent abc123"
exit 0
""")
    result = subprocess.run([script], capture_output=True, text=True)
    assert "Authenticating" in result.stdout
    assert "Deleting torrent" in result.stdout
    os.remove(script)

@SKIP_DIRECT_SHELL_ON_WINDOWS
def test_run_post_download_sh(monkeypatch):
    log_path = Path(tempfile.gettempdir()) / "post_download_test.log"
    if log_path.exists():
        log_path.unlink()

    script = write_script("run_post_download.sh", f"""#!/bin/bash
echo "Notifying about $1"
sleep 0
echo "Deleting completed torrent..."
echo "$(date): Finished $1" >> "{log_path}"
""")
    name = "TestTorrent"
    result = subprocess.run([script, name], capture_output=True, text=True)
    assert "Notifying about" in result.stdout
    assert log_path.exists()
    log_path.unlink()
    os.remove(script)


def test_post_download_hooks_prefer_root_env():
    for script_name in ("notify_complete.sh", "delete_completed.sh"):
        content = (PROJECT_ROOT / "scripts" / script_name).read_text(encoding="utf-8")
        assert content.index('[ -f "$ROOT_ENV_PATH" ]') < content.index('[ -f "$BOT_ENV_PATH" ]')
        assert content.index('[ -f "$BOT_ENV_PATH" ]') < content.index('[ -f "$SCRIPT_ENV_PATH" ]')
        assert "/opt/telegrambot" not in content


def test_post_download_hooks_do_not_log_to_read_only_scripts_dir():
    for script_name in ("notify_complete.sh", "run_post_download.sh"):
        content = (PROJECT_ROOT / "scripts" / script_name).read_text(encoding="utf-8")
        assert "/config/post_download.log" in content
        assert 'LOG_FILE="${POST_DOWNLOAD_LOG_FILE:-$DEFAULT_LOG_FILE}"' in content


def test_run_post_download_continues_when_notification_fails():
    content = (PROJECT_ROOT / "scripts" / "run_post_download.sh").read_text(encoding="utf-8")
    assert '"$SCRIPT_DIR/notify_complete.sh" "${1:-Unknown}" ||' in content
    assert content.index('"$SCRIPT_DIR/notify_complete.sh" "${1:-Unknown}" ||') < content.index('"$SCRIPT_DIR/delete_completed.sh"')
