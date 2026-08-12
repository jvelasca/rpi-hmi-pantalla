"""Check Pi after reboot - verify HMI services and backend.

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

    print("Connecting to Pi...")
    for attempt in range(10):
        try:
            ssh.connect(
                host=HOST,
                user=USER,
                password=PASSWORD,
                port=PORT,
                key_path=KEY_PATH,
                timeout=10,
            )
            print(f"Connected on attempt {attempt + 1}")
            break
        except Exception:
            if attempt < 9:
                print(f"  Attempt {attempt + 1} failed, retrying...")
                time.sleep(5)
            else:
                print("ERROR: Could not connect to Pi after 10 attempts")
                sys.exit(1)

    try:

        def sh(cmd: str, timeout: int = 15) -> tuple[str, str]:
            result = ssh.execute(cmd, timeout=timeout)
            return result.stdout.strip(), result.stderr.strip()

        print("\n=== Systemd services ===")
        out, err = sh("systemctl is-active rpi-hmi-backend.service")
        print(f"  backend: {out}")
        out, err = sh("systemctl is-active rpi-hmi-display.service")
        print(f"  display: {out}")
        out, err = sh("systemctl is-active lightdm")
        print(f"  lightdm: {out}")

        print("\n=== Backend health ===")
        out, err = sh("curl -s http://localhost:8000/health")
        print(f"  {out}")

        print("\n=== Display DRM ===")
        out, err = sh(
            "sudo fuser /dev/dri/card0 2>/dev/null | xargs ps -p 2>/dev/null | tail -5 || echo 'free'"
        )
        print(f"  card0 users:\n  {out}")

        print("\n=== IP ===")
        out, err = sh("hostname -I")
        print(f"  {out.strip()}")

        print("\n=== Web server test ===")
        out, err = sh("curl -s http://localhost:8000/ | head -5 || echo 'no-content'")
        print(f"  {out[:200]}")

    finally:
        ssh.disconnect()

    print("\n[DONE]")


if __name__ == "__main__":
    main()
