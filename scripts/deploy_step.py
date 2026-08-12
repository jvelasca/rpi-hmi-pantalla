"""Quick test of display app on Pi - step by step.

Credentials are loaded from environment variables (.env file)
or from RPI_HOST, RPI_USER, RPI_PASSWORD, RPI_KEY_PATH env vars.
"""
import os
import sys
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

        def run(cmd: str, timeout: int = 15) -> tuple[str, str]:
            result = ssh.execute(cmd, timeout=timeout)
            return result.stdout.strip(), result.stderr.strip()

        # Test 1: widget imports with font fallback
        print("=== Test 1: widget fonts ===")
        o, e = run(
            "cd /home/pi/rpi_hmi && PYTHONPATH=/home/pi/rpi_hmi /home/pi/rpi_hmi/venv/bin/python3 -c "
            "'from display.ui.widgets import LedIndicator, ButtonWidget; import pygame; "
            'print("HAS_FREETYPE=", hasattr(pygame,"freetype")); '
            'print("font_init=", pygame.font.get_init()); '
            "pygame.font.init(); l = LedIndicator(10,50,180,230); "
            'print("widget OK")\' 2>&1',
            timeout=15,
        )
        print("out:", o)
        print("err:", e[:200] if e else "none")

        # Test 2: screen init with mock
        print("\n=== Test 2: screen mock ===")
        o, e = run(
            "cd /home/pi/rpi_hmi && PYTHONPATH=/home/pi/rpi_hmi /home/pi/rpi_hmi/venv/bin/python3 -c "
            "'from display.ui.screen import Screen; s=Screen(mock=True); ok=s.init(); "
            'print("screen:", ok, s.width, s.height, s.driver); s.cleanup()\' 2>&1',
            timeout=15,
        )
        print("out:", o)
        print("err:", e[:200] if e else "none")

        # Test 3: DisplayApp import
        print("\n=== Test 3: DisplayApp import ===")
        o, e = run(
            "cd /home/pi/rpi_hmi && PYTHONPATH=/home/pi/rpi_hmi /home/pi/rpi_hmi/venv/bin/python3 -c "
            "'from display.app import DisplayApp; print(\"DisplayApp imported OK\")' 2>&1",
            timeout=15,
        )
        print("out:", o)
        print("err:", e[:200] if e else "none")

        # Test 4: Run app briefly (3s)
        print("\n=== Test 4: app run 3s ===")
        o, e = run(
            "cd /home/pi/rpi_hmi && PYTHONPATH=/home/pi/rpi_hmi "
            "timeout 3 /home/pi/rpi_hmi/venv/bin/python3 display/app.py 2>&1; echo '---DONE---'",
            timeout=10,
        )
        print("stdout:", o[:400])
        if e:
            print("stderr:", e[:400])

    finally:
        ssh.disconnect()


if __name__ == "__main__":
    main()
