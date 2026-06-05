
import pytest
from unittest.mock import patch, MagicMock
import bot.utils as utils

def test_get_disk_space(monkeypatch):
    monkeypatch.setattr("shutil.disk_usage", lambda _: (0, 0, 50 * 1024**3))  # 50 GB free
    result = utils.get_disk_space()
    assert "50 GB" in result

def test_get_ram_usage(monkeypatch):
    mock_mem = MagicMock()
    mock_mem.used = 2 * 1024**3
    mock_mem.total = 4 * 1024**3
    monkeypatch.setattr("psutil.virtual_memory", lambda: mock_mem)

    result = utils.get_ram_usage()
    assert "2048 MB / 4096 MB" in result

def test_get_cpu_usage(monkeypatch):
    monkeypatch.setattr(utils.os, "getloadavg", lambda: (1.23, 0.98, 0.0), raising=False)
    monkeypatch.setattr("psutil.cpu_percent", lambda: 37.5)

    result = utils.get_cpu_usage()
    assert "37.5%" in result and "1.23" in result

def test_get_cpu_usage_without_load_average(monkeypatch):
    monkeypatch.delattr(utils.os, "getloadavg", raising=False)
    monkeypatch.setattr("psutil.cpu_percent", lambda: 37.5)

    result = utils.get_cpu_usage()
    assert result == "37.5%"

def test_check_service_running(monkeypatch):
    monkeypatch.setattr("subprocess.check_output", lambda *a, **kw: b"active")
    assert utils.check_service("dummy") == "✅ Running"

def test_check_service_stopped(monkeypatch):
    monkeypatch.setattr("subprocess.check_output", lambda *a, **kw: b"inactive")
    assert utils.check_service("dummy") == "❌ Stopped"

def test_check_service_error(monkeypatch):
    monkeypatch.setattr("subprocess.check_output", lambda *a, **kw: (_ for _ in ()).throw(Exception("fail")))
    assert utils.check_service("dummy") == "❌ Unknown"

def test_check_url_status(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    monkeypatch.setattr("requests.get", lambda *a, **kw: mock_resp)
    assert utils.check_url_status("http://test") == "✅ Online"

def test_check_url_status_fail(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **kw: (_ for _ in ()).throw(Exception("fail")))
    assert utils.check_url_status("http://test") == "❌ Down"

def test_check_telegram_api(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    monkeypatch.setattr("requests.get", lambda *a, **kw: mock_resp)
    assert utils.check_telegram_api("dummy") == "✅ Online"

def test_check_telegram_api_down(monkeypatch):
    monkeypatch.setattr("requests.get", lambda *a, **kw: (_ for _ in ()).throw(Exception("fail")))
    assert utils.check_telegram_api("dummy") == "❌ Down"
