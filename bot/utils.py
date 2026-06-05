import os
import shutil
import subprocess
import psutil
import requests

def get_disk_space():
    _, _, free = shutil.disk_usage("/")
    return f"{free // (1024 ** 3)} GB free"

def get_ram_usage():
    mem = psutil.virtual_memory()
    return f"{mem.used // (1024 ** 2)} MB / {mem.total // (1024 ** 2)} MB"

def get_cpu_usage():
    try:
        load1, load5, _ = os.getloadavg()
        load_txt = f"(Load: {load1:.2f}, {load5:.2f})"
    except Exception:
        load_txt = ""
    return f"{psutil.cpu_percent()}% {load_txt}".strip()

def check_service(name: str) -> str:
    """
    Returns '✅ Running' if systemd service is active, else '❌ Stopped'.
    Matches your existing emoji style so handlers.py can drop it in directly.
    """
    try:
        status = subprocess.check_output(
            ["systemctl", "is-active", name],
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode().strip()
        return "✅ Running" if status == "active" else "❌ Stopped"
    except Exception:
        return "❌ Unknown"

def check_url_status(url: str) -> str:
    try:
        r = requests.get(url, timeout=3)
        return "✅ Online" if r.status_code == 200 else "❌ Error"
    except Exception:
        return "❌ Down"

def check_telegram_api(token: str) -> str:
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=3)
        return "✅ Online" if r.status_code == 200 else "❌ Error"
    except Exception:
        return "❌ Down"
