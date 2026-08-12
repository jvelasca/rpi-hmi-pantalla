"""Deploy frontend build to Pi (SFTP frontend/dist/ -> /home/pi/rpi_hmi/frontend/dist/).

FastAPI sirve el frontend directamente desde frontend/dist/ en la Pi
(main.py monta ese directorio en la raiz con StaticFiles html=True).

Credentials are loaded from environment variables (.env file)
or from RPI_HOST, RPI_USER, RPI_PASSWORD, RPI_KEY_PATH env vars.

Usage:
    python scripts/deploy_frontend.py
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
PI_BASE = "/home/pi/rpi_hmi"
DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"


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

    if not DIST.exists():
        sys.exit(f"ERROR: {DIST} no existe. Ejecuta: cd frontend && npm run build")

    try:
        target_dir = f"{PI_BASE}/frontend/dist"

        # Clean and recreate target directory
        ssh.execute(f"rm -rf {target_dir} && mkdir -p {target_dir}", timeout=10)
        print(f"  Cleaned {target_dir}/")

        # Upload files via SFTP
        count = 0
        for local_file in sorted(DIST.rglob("*")):
            if local_file.is_dir():
                continue
            rel = local_file.relative_to(DIST).as_posix()
            remote_path = f"{target_dir}/{rel}"

            # Ensure subdirectories exist
            remote_parent = str(Path(remote_path).parent)
            ssh.execute(f"mkdir -p {remote_parent}", timeout=5)

            try:
                ssh.transfer_file(str(local_file), remote_path)
                size = local_file.stat().st_size
                print(f"  OK  frontend/dist/{rel} ({size}B)")
                count += 1
            except Exception as e:
                print(f"  ERR {rel}: {e}")

        # Verify
        print(f"\n  Files on Pi ({target_dir}/):")
        result = ssh.execute(f"find {target_dir} -type f -ls 2>/dev/null", timeout=10)
        print(result.stdout)

        # Check root page serves the new frontend
        print("\n  Root page (index.html):")
        result = ssh.execute("curl -s http://localhost:8000/ | head -1", timeout=10)
        print("  " + (result.stdout.strip()[:120] if result.stdout.strip() else "(empty)"))

        # Restart backend to pick up new frontend (in case of cached static files)
        print("\n  Restarting backend...")
        ssh.execute("sudo systemctl restart rpi-hmi-backend.service 2>/dev/null || true", timeout=15)
        print("  Backend restarted")

        print(f"\n[DONE] {count} files -> http://{HOST}:8000/")

    finally:
        ssh.disconnect()


if __name__ == "__main__":
    main()
