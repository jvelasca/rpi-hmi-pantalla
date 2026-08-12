"""Check all deps and test display app on Pi.

Credentials are loaded from environment variables (.env file)
or from RPI_HOST, RPI_USER, RPI_PASSWORD, RPI_KEY_PATH env vars.
"""
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from backend.app.services.ssh_manager import ParamikoSSHDriver  # noqa: E402

HOST = os.getenv("RPI_HOST", "192.168.88.211")
USER = os.getenv("RPI_USER", "pi")
PASSWORD = os.getenv("RPI_PASSWORD", "")
KEY_PATH = os.getenv("RPI_KEY_PATH", "")
PORT = int(os.getenv("RPI_PORT", "22"))


def main() -> None:
    ssh = ParamikoSSHDriver()

    if not KEY_PATH and not PASSWORD:
        sys.exit("ERROR: Define RPI_PASSWORD o RPI_KEY_PATH en .env")

    ssh.connect(
        host=HOST,
        user=USER,
        password=PASSWORD,
        port=PORT,
        key_path=KEY_PATH,
        timeout=15,
    )
    print(f"[OK] Connected to {HOST}")

    try:
        # Check evdev and websocket
        result = ssh.execute(
            "/home/pi/rpi_hmi/venv/bin/python3 -c "
            "'import evdev; print(\"evdev OK\"); "
            "import websocket; print(\"ws OK\"); "
            "import requests; print(\"requests OK\")'",
            timeout=15,
        )
        print("[DEPS]", result.stdout.strip())
        if result.stderr:
            print("[STDERR]", result.stderr[:300])

        # Quick test run (5 sec timeout, mock mode to avoid DRM issues)
        print("\n[RUNTEST] Running display app (5s)...")
        result = ssh.execute(
            "cd /home/pi/rpi_hmi && PYTHONPATH=/home/pi/rpi_hmi "
            "timeout 6 /home/pi/rpi_hmi/venv/bin/python3 display/app.py --debug 2>&1 || true",
            timeout=15,
        )
        print(result.stdout[-600:])
        if result.stderr:
            print("[STDERR]", result.stderr[-400:])

    finally:
        ssh.disconnect()


if __name__ == "__main__":
    main()
