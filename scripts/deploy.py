"""Deploy + verify display app to Raspberry Pi in one shot.

Credentials are loaded from environment variables (.env file)
or from RPI_HOST, RPI_USER, RPI_PASSWORD, RPI_PORT env vars.

Uses the project's own SSHDriver and DeployService instead of
raw paramiko, eliminating SSH/SFTP logic duplication.

Paths unificados: /home/pi/rpi_hmi con venv/ para todo.

Usage:
    python scripts/deploy.py                     # deploy + verify
    python scripts/deploy.py --run               # deploy + run display app (solo Pi!)
    python scripts/deploy.py --hmi               # deploy, stop lightdm, run HMI en TFT
    python scripts/deploy.py --verify            # solo verificar estado
    python scripts/deploy.py --install-service   # instalar systemd services (arranque automatico)
"""

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Cargar .env desde raiz del proyecto
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from backend.app.services.ssh_manager import ParamikoSSHDriver
from backend.app.services.deploy_service import DeployService

HOST = os.getenv("RPI_HOST", "192.168.88.211")
USER = os.getenv("RPI_USER", "pi")
PASSWORD = os.getenv("RPI_PASSWORD", "")
KEY_PATH = os.getenv("RPI_KEY_PATH", "")
PORT = int(os.getenv("RPI_PORT", "22"))

# ── Paths unificados ──────────────────────────────────────────
PI_BASE = "/home/pi/rpi_hmi"
VENV_PY = f"{PI_BASE}/venv/bin/python3"
ROOT = Path(__file__).resolve().parents[1]


def connect_ssh() -> ParamikoSSHDriver:
    """Crea y conecta un SSHDriver usando credenciales del entorno.

    Returns:
        SSHDriver conectado a la Raspberry Pi.

    Raises:
        SystemExit: Si faltan credenciales.
    """
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
    return ssh


def step(msg: str) -> None:
    print(f"\n{'='*55}\n  {msg}\n{'='*55}")


# ── Health check helpers ──────────────────────────────────────


def check_backend_ready(ssh: ParamikoSSHDriver) -> bool:
    """Verifica que el backend esta listo usando /health/ready.

    Usa codigo HTTP (200 = OK), no grep de texto.
    """
    result = ssh.execute(
        "curl -fsS -o /dev/null -w '%{http_code}' "
        "http://localhost:8000/health/ready 2>/dev/null || echo 'FAIL'",
        timeout=10,
    )
    return result.ok and result.stdout.strip() == "200"


# ── Display-specific operations ───────────────────────────────


def deploy_display_files(ssh: ParamikoSSHDriver) -> int:
    """Sync display/ files to Pi via SFTP using SSHDriver (solo changed)."""
    DISPLAY_DIR = ROOT / "display"
    count = 0
    for py_file in sorted(DISPLAY_DIR.rglob("*")):
        if "__pycache__" in py_file.parts:
            continue
        if py_file.suffix == ".pyc":
            continue
        if py_file.is_dir():
            continue
        rel = str(py_file.relative_to(ROOT)).replace("\\", "/")
        remote = f"{PI_BASE}/{rel}"
        try:
            parent = str(Path(remote).parent)
            ssh.execute(f"mkdir -p {parent}", timeout=10)

            local_time = py_file.stat().st_mtime
            result = ssh.execute(
                f"stat -c %Y {remote} 2>/dev/null || echo '0'",
                timeout=10,
            )
            remote_time = float(result.stdout.strip() or "0")
            if local_time <= remote_time:
                continue

            ssh.transfer_file(str(py_file), remote)
            size = py_file.stat().st_size
            print(f"  OK  {rel} ({size}B)")
            count += 1
        except Exception as exc:
            print(f"  ERR {rel}: {exc}")
    print(f"  Total: {count} files synced")
    return count


def deploy_scripts(ssh: ParamikoSSHDriver) -> None:
    """Sync scripts/ to Pi (start_hmi.sh, etc.)."""
    SCRIPTS_DIR = ROOT / "scripts"
    ssh.execute(f"mkdir -p {PI_BASE}/scripts", timeout=10)
    for script_file in SCRIPTS_DIR.glob("*"):
        if script_file.name.endswith(".pyc") or script_file.name == "__pycache__":
            continue
        rel = str(script_file.relative_to(ROOT)).replace("\\", "/")
        remote = f"{PI_BASE}/{rel}"
        ssh.transfer_file(str(script_file), remote)
        if script_file.suffix == ".sh":
            ssh.execute(f"chmod +x {remote}", timeout=10)
            print(f"  OK  {rel} (chmod +x)")
        else:
            print(f"  OK  {rel} ({script_file.stat().st_size}B)")


def install_display_deps(ssh: ParamikoSSHDriver) -> None:
    """Install missing Python packages for display in venv."""
    needed = []
    for mod in ["pygame", "evdev", "requests", "websocket"]:
        result = ssh.execute(f"{VENV_PY} -c 'import {mod}' 2>&1", timeout=10)
        if not result.ok:
            needed.append(mod)

    if needed:
        print(f"  Installing: {', '.join(needed)}")
        result = ssh.execute(
            f"source {PI_BASE}/venv/bin/activate && pip install {' '.join(needed)} 2>&1 | tail -3",
            timeout=300,
        )
        print(f"  pip exit={result.exit_code}")
    else:
        print("  All deps already installed")

    verify_cmd = (
        f"{VENV_PY} -c 'import pygame,evdev,requests,websocket; "
        "print(f\"pygame={pygame.version.ver}, evdev OK, "
        "req={requests.__version__}, ws={websocket.__version__}\")' 2>&1"
    )
    result = ssh.execute(verify_cmd, timeout=15)
    print(f"  [verify] {result.stdout}")
    if result.stderr:
        print(f"  [stderr] {result.stderr[:100]}")


def verify(ssh: ParamikoSSHDriver) -> None:
    """Run verification checks."""
    # Health (usa /health/ready con HTTP status)
    result = ssh.execute("curl -fsS http://localhost:8000/health 2>/dev/null || echo 'UNREACHABLE'", timeout=10)
    print(f"  Backend health: {result.stdout[:200]}")

    # Check ready endpoint
    if check_backend_ready(ssh):
        print("  Ready: YES")
    else:
        print("  Ready: NO")

    # Display devices
    result = ssh.execute(
        "ls -la /dev/dri/card0 /dev/fb1 /dev/input/event0 2>&1",
        timeout=10,
    )
    print(f"  Devices:\n{result.stdout}")

    # Check if lightdm is running
    result = ssh.execute(
        "systemctl is-active lightdm 2>&1 || echo 'inactive'",
        timeout=10,
    )
    print(f"  lightdm: {result.stdout.strip()}")

    # Check DRM card0 users
    result = ssh.execute(
        "sudo fuser /dev/dri/card0 2>/dev/null | xargs ps -p 2>/dev/null | tail -3 || echo 'free'",
        timeout=10,
    )
    print(f"  DRM card0 users:\n{result.stdout}")

    # Import chain
    cmd = (
        f"cd {PI_BASE} && PYTHONPATH={PI_BASE} {VENV_PY} -c '"
        "from display.ui.theme import BACKGROUND; "
        "from display.ui.touch import TouchHandler; "
        "from display.ui.widgets import LedIndicator, ButtonWidget; "
        "from display.ui.screen import Screen; "
        "from display.app import DisplayApp; "
        "print(\"ALL IMPORTS OK\")' 2>&1"
    )
    result = ssh.execute(cmd, timeout=15)
    print(f"  Import chain: {'OK' if 'ALL IMPORTS OK' in result.stdout else 'FAIL'}")
    if result.stderr:
        print(f"  [stderr] {result.stderr[:200]}")


def ensure_backend(ssh: ParamikoSSHDriver) -> None:
    """Start backend via systemctl if not already running.

    Usa /health/ready (codigo HTTP 200) en lugar de grep -q ok.
    """
    if check_backend_ready(ssh):
        print("  Backend already running and ready")
        return

    print("  Starting backend via systemctl...")
    ssh.execute(
        "sudo systemctl start rpi-hmi-backend.service 2>&1 || "
        f"cd {PI_BASE} && PYTHONPATH={PI_BASE} nohup {VENV_PY} "
        f"-m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 "
        f"> /tmp/backend.log 2>&1 &",
        timeout=15,
    )
    time.sleep(3)

    if check_backend_ready(ssh):
        print("  Backend start: OK")
    else:
        print("  Backend start: FAIL (check /tmp/backend.log)")


def stop_lightdm(ssh: ParamikoSSHDriver) -> bool:
    """Stop lightdm to free /dev/dri/card0."""
    result = ssh.execute(
        "systemctl is-active lightdm 2>&1 || echo 'inactive'",
        timeout=10,
    )
    if "active" not in result.stdout:
        print("  lightdm already stopped")
        return True

    print("  Stopping lightdm...")
    ssh.execute("sudo systemctl stop lightdm", timeout=10)
    time.sleep(2)

    result = ssh.execute(
        "sudo fuser /dev/dri/card0 2>/dev/null || echo 'free'",
        timeout=10,
    )
    if "free" in result.stdout:
        print("  lightdm stopped, /dev/dri/card0 liberated")
        return True
    else:
        print(f"  [WARN] /dev/dri/card0 still in use by: {result.stdout}")
        ssh.execute("sudo fuser -k /dev/dri/card0 2>/dev/null || true", timeout=10)
        time.sleep(1)
        return True


def unbind_console(ssh: ParamikoSSHDriver) -> None:
    """Unbind vtcon1 from fb1 (ili9486)."""
    result = ssh.execute(
        "test -w /sys/class/vtconsole/vtcon1/bind && "
        "echo 0 | sudo tee /sys/class/vtconsole/vtcon1/bind > /dev/null 2>&1 && "
        "echo 'vtcon1 unbound' || echo 'vtcon1 not available'",
        timeout=10,
    )
    print(f"  Console: {result.stdout.strip()}")


def ensure_video_group(ssh: ParamikoSSHDriver) -> None:
    """Add pi user to video group if needed."""
    result = ssh.execute(
        "groups pi | grep -q video && echo 'yes' || echo 'no'",
        timeout=10,
    )
    if "yes" in result.stdout:
        print("  pi already in video group")
        return
    print("  Adding pi to video group...")
    ssh.execute("sudo usermod -a -G video pi", timeout=10)
    print("  Done. May need to logout/login for group to take effect.")


def run_hmi(ssh: ParamikoSSHDriver) -> None:
    """Run HMI app on Pi display (DRM/KMS)."""
    step("RUN HMI ON TFT DISPLAY")
    stop_lightdm(ssh)
    unbind_console(ssh)
    ensure_video_group(ssh)

    print("\n  Launching display/app.py on Pi TFT (ili9486)...")
    print("  Press Ctrl+C to stop.\n")

    cmd = (
        f"cd {PI_BASE} && "
        f"SDL_VIDEODRIVER=kmsdrm SDL_KMSDRM_DEVICE_INDEX=0 "
        f"PYTHONPATH={PI_BASE} PYTHONUNBUFFERED=1 "
        f"{VENV_PY} -m display.app --api-url http://localhost:8000 --debug"
    )
    # Interactive session via SSH driver
    try:
        result = ssh.execute(cmd, timeout=3600)
        print(f"\n  HMI finished: exit_code={result.exit_code}")
    except KeyboardInterrupt:
        print("\n  Stopped by user")


def install_services(ssh: ParamikoSSHDriver) -> None:
    """Install systemd services on Pi (backend + display)."""
    CONFIG_DIR = ROOT / "config"

    ssh.execute(f"mkdir -p {PI_BASE}/config/systemd", timeout=10)
    for svc_file in (CONFIG_DIR / "systemd").glob("*.service"):
        rel = str(svc_file.relative_to(ROOT)).replace("\\", "/")
        remote = f"{PI_BASE}/{rel}"
        ssh.transfer_file(str(svc_file), remote)
        print(f"  Uploaded {svc_file.name}")

        target = f"/etc/systemd/system/{svc_file.name}"
        ssh.execute(f"sudo cp {remote} {target}", timeout=10)
        print(f"  Installed {target}")

    ssh.execute("sudo systemctl daemon-reload", timeout=10)
    print("  systemd daemon-reload done")

    ssh.execute(
        "sudo systemctl enable rpi-hmi-backend.service rpi-hmi-display.service",
        timeout=10,
    )
    print("  Services enabled")

    ssh.execute("sudo systemctl disable lightdm 2>&1 || true", timeout=10)
    print("  lightdm disabled")

    print("\n  [DONE] Services installed. Reboot to start HMI on TFT:")
    print(f"    ssh {USER}@{HOST} sudo reboot")


def main() -> None:
    p = argparse.ArgumentParser(description="RPi HMI deploy script")
    p.add_argument("--run", action="store_true",
                   help="Run display app on Pi (requires console)")
    p.add_argument("--hmi", action="store_true",
                   help="Stop lightdm, run HMI on Pi TFT display")
    p.add_argument("--verify", action="store_true",
                   help="Only verify, no deploy")
    p.add_argument("--install-service", action="store_true",
                   help="Install systemd services + disable lightdm")
    args = p.parse_args()

    ssh = connect_ssh()
    deploy_svc = DeployService(ssh, remote_root=PI_BASE)

    try:
        if args.verify:
            step("VERIFICATION")
            verify(ssh)
            return

        if args.install_service:
            step("DEPLOY BACKEND")
            deploy_svc.deploy_app(project_root=str(ROOT))
            step("DEPLOY DISPLAY FILES")
            deploy_display_files(ssh)
            deploy_scripts(ssh)
            step("INSTALL DEPS")
            install_display_deps(ssh)
            step("INSTALL SYSTEMD SERVICES")
            install_services(ssh)
            return

        if args.hmi:
            step("DEPLOY BACKEND")
            deploy_svc.deploy_app(project_root=str(ROOT))
            step("DEPLOY DISPLAY FILES")
            deploy_display_files(ssh)
            deploy_scripts(ssh)
            step("INSTALL DEPS")
            install_display_deps(ssh)
            run_hmi(ssh)
            return

        # Default: deploy + verify
        step("ENSURE BACKEND")
        ensure_backend(ssh)

        step("DEPLOY FILES (Backend)")
        deploy_svc.deploy_app(project_root=str(ROOT))
        step("DEPLOY FILES (Display)")
        deploy_display_files(ssh)
        deploy_scripts(ssh)

        step("INSTALL DEPS")
        install_display_deps(ssh)

        step("VERIFY")
        verify(ssh)

        if args.run:
            step("RUN DISPLAY APP (Ctrl+C to stop)")
            print("  Running display/app.py on Pi...")
            cmd = (
                f"cd {PI_BASE} && PYTHONPATH={PI_BASE} {VENV_PY} "
                f"display/app.py"
            )
            ssh.execute(cmd, timeout=600)

    finally:
        ssh.disconnect()

    print("\n[DONE]")


if __name__ == "__main__":
    main()
