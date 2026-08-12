"""Deploy frontend build to Pi via DeployService (SFTP dist/ -> backend/app/static/).

Credentials are loaded from environment variables (.env file)
or from RPI_HOST, RPI_USER, RPI_PASSWORD, RPI_KEY_PATH env vars.

Uses the project's own SSHDriver and DeployService instead of
raw paramiko, eliminating SSH/SFTP logic duplication.

Usage:
    python scripts/deploy_frontend.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from backend.app.services.ssh_manager import ParamikoSSHDriver, SSHResult  # noqa: E402
from backend.app.services.deploy_service import DeployService  # noqa: E402

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

    try:
        deploy_svc = DeployService(ssh, remote_root=PI_BASE)
        static_dir = f"{PI_BASE}/backend/app/static"

        # Clean and create static directory
        result = ssh.execute(
            f"rm -rf {static_dir}/* && mkdir -p {static_dir}/assets",
            timeout=10,
        )
        print("  Cleaned static/")

        # Upload files via DeployService SFTP
        count = 0
        for local_file in sorted(DIST.rglob("*")):
            if local_file.is_dir():
                continue
            rel = local_file.relative_to(DIST).as_posix()
            remote_path = f"{static_dir}/{rel}"
            try:
                ssh.transfer_file(str(local_file), remote_path)
                size = local_file.stat().st_size
                print(f"  OK  static/{rel} ({size}B)")
                count += 1
            except Exception as e:
                print(f"  ERR {rel}: {e}")

        # Verify
        print("\n  Files on Pi:")
        result = ssh.execute(
            f"find {static_dir} -type f -ls 2>/dev/null",
            timeout=10,
        )
        print(result.stdout)

        # Check root page serves the new frontend
        print("\n  Root page:")
        result = ssh.execute("curl -s http://localhost:8000/", timeout=10)
        html = result.stdout
        print("  " + html.split("\n")[0][:80])

        print(f"\n[DONE] {count} files -> http://{HOST}:8000/")

    finally:
        ssh.disconnect()


if __name__ == "__main__":
    main()
