"""Rollback manager for RPi HMI deployments.

Creates timestamped backups of the deployed application on the
Raspberry Pi before deploys and allows restoring to any previous
version.

Backups are stored as tar.gz archives on the Pi in:
    /home/pi/rpi_hmi_backups/

Usage:
    python scripts/rollback.py --backup       Create a backup snapshot
    python scripts/rollback.py --list         List available backups
    python scripts/rollback.py --restore      Restore the latest backup
    python scripts/rollback.py --restore NAME Restore a specific backup
    python scripts/rollback.py --clean N      Keep only the last N backups
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from backend.app.services.ssh_manager import ParamikoSSHDriver

HOST = os.getenv("RPI_HOST", "192.168.88.211")
USER = os.getenv("RPI_USER", "pi")
PASSWORD = os.getenv("RPI_PASSWORD", "")
KEY_PATH = os.getenv("RPI_KEY_PATH", "")
PORT = int(os.getenv("RPI_PORT", "22"))
PI_BASE = "/home/pi/rpi_hmi"
BACKUP_BASE = "/home/pi/rpi_hmi_backups"


def _connect() -> ParamikoSSHDriver:
    """Connect to the Raspberry Pi using credentials from the environment."""
    ssh = ParamikoSSHDriver()
    if not KEY_PATH and not PASSWORD:
        sys.exit("ERROR: Set RPI_PASSWORD or RPI_KEY_PATH in .env")

    ssh.connect(
        host=HOST,
        user=USER,
        password=PASSWORD,
        port=PORT,
        key_path=KEY_PATH,
        timeout=15,
    )
    print(f"[OK] Connected to {HOST}")
    return ssh


def cmd_backup(ssh: ParamikoSSHDriver) -> None:
    """Create a timestamped backup of the current deployment."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = f"rpi_hmi_{timestamp}"
    backup_path = f"{BACKUP_BASE}/{backup_name}"
    archive = f"{backup_path}.tar.gz"

    print(f"\n  Creating backup: {backup_name}")

    result = ssh.execute(
        f"test -d {PI_BASE} && echo 'exists' || echo 'missing'",
        timeout=10,
    )
    if "missing" in result.stdout:
        print(f"  [SKIP] {PI_BASE} does not exist — nothing to backup")
        return

    # Read current version if available
    version_result = ssh.execute(
        f"cat {PI_BASE}/.deploy_version 2>/dev/null || echo 'unknown'",
        timeout=10,
    )
    current_version = version_result.stdout.strip()

    # Ensure backup directory exists
    ssh.execute(f"mkdir -p {BACKUP_BASE}", timeout=10)

    # Create tar.gz archive of the deployment directory
    ssh.execute(
        f"tar -czf {archive} -C /home/pi rpi_hmi 2>&1",
        timeout=120,
    )

    # Write metadata
    metadata = f"version={current_version}\ntimestamp={timestamp}\n"
    ssh.execute(
        f"echo '{metadata}' > {backup_path}.meta",
        timeout=10,
    )

    # Check size
    size_result = ssh.execute(
        f"stat -c %s {archive} 2>/dev/null || echo '0'",
        timeout=10,
    )
    size_kb = int(size_result.stdout.strip()) // 1024

    print(f"  [OK] Backup created: {backup_name}.tar.gz ({size_kb} KB)")
    print(f"       Version: {current_version}")


def cmd_list(ssh: ParamikoSSHDriver) -> None:
    """List all available backups on the Pi."""
    result = ssh.execute(
        f"ls -1t {BACKUP_BASE}/*.tar.gz 2>/dev/null || echo 'none'",
        timeout=10,
    )

    archives = [line.strip() for line in result.stdout.splitlines() if line.strip() and line != "none"]

    if not archives:
        print("  No backups found.")
        return

    print(f"\n  Backups on {HOST} ({len(archives)} total):\n")
    for idx, archive in enumerate(archives, 1):
        name = Path(archive).stem  # rpi_hmi_20260811_220000
        meta_path = f"{BACKUP_BASE}/{name}.meta"

        # Get size
        size_result = ssh.execute(
            f"stat -c %s {archive} 2>/dev/null || echo '0'",
            timeout=10,
        )
        size_kb = int(size_result.stdout.strip()) // 1024

        # Get metadata
        meta_result = ssh.execute(
            f"cat {meta_path} 2>/dev/null || echo 'no meta'",
            timeout=10,
        )
        version = "unknown"
        for line in meta_result.stdout.splitlines():
            if line.startswith("version="):
                version = line.split("=", 1)[1]

        print(f"  {idx:>3}. {name}  ({size_kb} KB)  v{version}")


def cmd_restore(ssh: ParamikoSSHDriver, backup_name: str | None = None) -> None:
    """Restore a deployment from a backup archive.

    If backup_name is None, the latest backup is used.
    The current deployment is backed up first (safety snapshot).
    """
    if backup_name:
        archive = f"{BACKUP_BASE}/{backup_name}.tar.gz"
    else:
        # Find latest backup
        result = ssh.execute(
            f"ls -1t {BACKUP_BASE}/*.tar.gz 2>/dev/null | head -1 || echo 'none'",
            timeout=10,
        )
        latest = result.stdout.strip()
        if latest == "none":
            print("  [ERROR] No backups found.")
            return
        archive = latest
        backup_name = Path(archive).stem

    print(f"\n  Restoring from: {backup_name}")

    # Verify archive exists
    result = ssh.execute(
        f"test -f {archive} && echo 'ok' || echo 'missing'",
        timeout=10,
    )
    if "missing" in result.stdout:
        print(f"  [ERROR] Backup not found: {archive}")
        return

    # Create safety backup of current deployment before restoring
    safety_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safety_name = f"PRE_ROLLBACK_{safety_ts}"
    safety_archive = f"{BACKUP_BASE}/{safety_name}.tar.gz"

    check = ssh.execute(
        f"test -d {PI_BASE} && echo 'exists' || echo 'missing'",
        timeout=10,
    )
    if "exists" in check.stdout:
        print(f"  Creating safety backup: {safety_name}")
        ssh.execute(
            f"tar -czf {safety_archive} -C /home/pi rpi_hmi 2>&1",
            timeout=120,
        )

    # Stop running services
    print("  Stopping services...")
    ssh.execute(
        "sudo systemctl stop rpi-hmi-backend rpi-hmi-display 2>/dev/null || true",
        timeout=10,
    )

    # Remove current deployment
    print(f"  Removing current deployment at {PI_BASE}...")
    ssh.execute(f"rm -rf {PI_BASE}", timeout=10)

    # Extract backup
    print("  Extracting backup...")
    result = ssh.execute(
        f"tar -xzf {archive} -C /home/pi 2>&1",
        timeout=120,
    )
    if not result.ok:
        print(f"  [ERROR] Extraction failed:\n{result.stderr}")
        print(f"  Safety backup available at: {safety_name}")
        return

    # Read restored version
    version_result = ssh.execute(
        f"cat {PI_BASE}/.deploy_version 2>/dev/null || echo 'unknown'",
        timeout=10,
    )
    restored_version = version_result.stdout.strip()

    # Start services
    print("  Starting services...")
    ssh.execute(
        "sudo systemctl start rpi-hmi-backend 2>/dev/null || true",
        timeout=10,
    )

    print(f"\n  [OK] Restored to version: {restored_version}")
    print(f"       Safety backup: {safety_name}.tar.gz")
    print(f"       Display service will auto-start when backend is ready.")


def cmd_clean(ssh: ParamikoSSHDriver, keep: int) -> None:
    """Remove old backups, keeping only the last N."""
    result = ssh.execute(
        f"ls -1t {BACKUP_BASE}/*.tar.gz 2>/dev/null || echo 'none'",
        timeout=10,
    )

    archives = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip() and line != "none"
    ]

    if len(archives) <= keep:
        print(f"  {len(archives)} backups, keeping all (limit is {keep}).")
        return

    to_remove = archives[keep:]
    print(f"  Removing {len(to_remove)} old backup(s), keeping latest {keep}:")
    for archive in to_remove:
        name = Path(archive).stem
        ssh.execute(f"rm -f {archive} {BACKUP_BASE}/{name}.meta", timeout=10)
        print(f"    - {name}")

    print(f"  [OK] {len(archives) - len(to_remove)} backups remaining.")


def main() -> None:
    parser = argparse.ArgumentParser(description="RPi HMI rollback manager")
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a backup snapshot of the current deployment",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available backups on the Pi",
    )
    parser.add_argument(
        "--restore",
        nargs="?",
        const=None,
        metavar="BACKUP_NAME",
        help="Restore from a backup (latest if no name given)",
    )
    parser.add_argument(
        "--clean",
        type=int,
        metavar="N",
        help="Keep only the last N backups, remove older ones",
    )
    args = parser.parse_args()

    if not any([args.backup, args.list, args.restore is not None, args.clean]):
        parser.print_help()
        return

    ssh = _connect()
    try:
        if args.backup:
            cmd_backup(ssh)
        elif args.list:
            cmd_list(ssh)
        elif args.restore is not None:
            cmd_restore(ssh, args.restore)
        elif args.clean:
            cmd_clean(ssh, args.clean)
    finally:
        ssh.disconnect()


if __name__ == "__main__":
    main()
