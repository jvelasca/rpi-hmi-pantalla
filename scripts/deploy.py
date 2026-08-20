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
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Cargar .env desde raiz del proyecto
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Imports tras load_dotenv(): los modulos de backend leen settings del entorno al importar.
from backend.app.services.deploy_service import DeployService  # noqa: E402
from backend.app.services.ssh_manager import ParamikoSSHDriver  # noqa: E402

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


def _check_deploy_steps(steps, label="Deploy"):
    """Verifica que todos los pasos de deploy fueron exitosos."""
    failed = [s for s in steps if not s.success]
    if failed:
        print(f"\n[ERROR] {label}: {len(failed)} archivo(s) no se copiaron:")
        for f in failed:
            print(f"  - {f.step}: {f.message}")
        sys.exit(1)


def _build_frontend(root: Path) -> None:
    """Compila el frontend (npm run build) siempre.

    En deploy nunca se salta la compilacion para evitar enviar
    una version obsoleta del frontend.
    """
    frontend_dir = root / "frontend"

    print("  Compilando frontend con npm run build...")
    try:
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(frontend_dir),
            check=True,
            capture_output=False,  # Show build output
        )
        print("  Frontend compilado OK")
    except subprocess.CalledProcessError:
        print("[ERROR] Fallo la compilacion del frontend (npm run build)")
        sys.exit(1)


def _ensure_scripts_executable(ssh: ParamikoSSHDriver) -> list:
    """Aplica chmod +x a los .sh en PI_BASE/scripts/ (ya desplegados por DeployService).

    Returns:
        Lista de errores (vacia si todo OK).
    """
    errors = []
    result = ssh.execute(
        f"find {PI_BASE}/scripts -name '*.sh' -type f 2>/dev/null",
        timeout=10,
    )
    if not result.ok:
        errors.append(f"find failed: {result.stderr.strip()}")
        return errors

    sh_files = [f.strip() for f in result.stdout.split("\n") if f.strip()]
    for sh_file in sh_files:
        try:
            chmod_result = ssh.execute(f"chmod +x {sh_file}", timeout=10)
            if chmod_result.ok:
                print(f"  OK  chmod +x {sh_file}")
            else:
                errors.append(f"{sh_file}: {chmod_result.stderr.strip()}")
        except Exception as exc:
            errors.append(f"{sh_file}: {exc}")

    if not errors:
        print(f"  Scripts executables: {len(sh_files)} .sh files")

    return errors


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


def install_display_deps(ssh: ParamikoSSHDriver) -> bool:
    """Install display dependencies from requirements file.

    Returns:
        True if successful, False if error.
    """
    req_path = f"{PI_BASE}/display/requirements.txt"
    # Check if requirements file exists
    result = ssh.execute(f"test -f {req_path} && echo 'FOUND' || echo 'MISSING'", timeout=10)
    if "MISSING" in result.stdout:
        print(f"  [ERROR] {req_path} not found on Pi. Deploy display files first.")
        return False

    print(f"  Installing from {req_path}...")
    result = ssh.execute(
        f"{VENV_PY} -m pip install -r {req_path} 2>&1 | tail -5",
        timeout=300,
    )
    print(f"  pip exit={result.exit_code}")
    print(f"  {result.stdout.strip()}")

    if result.exit_code != 0:
        print(f"  [ERROR] pip install failed with exit code {result.exit_code}")
        return False
    return True


def verify(ssh: ParamikoSSHDriver) -> None:
    """Run verification checks."""
    # Health (usa /health/ready con HTTP status)
    result = ssh.execute(
        "curl -fsS http://localhost:8000/health 2>/dev/null || echo 'UNREACHABLE'", timeout=10
    )
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


def ensure_backend(ssh: ParamikoSSHDriver) -> bool:
    """Start backend via systemctl if not already running.

    Usa /health/ready (codigo HTTP 200) en lugar de grep -q ok.

    Returns:
        True si el backend esta corriendo al finalizar.
    """
    if check_backend_ready(ssh):
        print("  Backend already running and ready")
        return True

    print("  Starting backend via systemctl...")
    result = ssh.execute(
        "sudo systemctl start rpi-hmi-backend.service 2>&1 && echo 'STARTED' || echo 'FAILED'",
        timeout=15,
    )

    if "STARTED" in result.stdout:
        time.sleep(3)
        if check_backend_ready(ssh):
            print("  Backend start: OK")
            return True

    print("  Backend start: FAIL (check journalctl -u rpi-hmi-backend)")
    return False


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

        # ── Unified deploy flow (all paths share steps 1-7) ──

        # 1. Setup environment
        step("SETUP ENVIRONMENT")
        env_steps = deploy_svc.setup_environment()
        _check_deploy_steps(env_steps, "Environment setup")

        # 2. Build frontend locally (must run before deploy_app which transfers frontend/dist/)
        step("BUILD FRONTEND")
        _build_frontend(ROOT)

        # 3. Deploy ALL files (backend, display, scripts, frontend/dist, config)
        step("DEPLOY FILES")
        app_steps = deploy_svc.deploy_app(project_root=str(ROOT))
        _check_deploy_steps(app_steps, "Deploy")

        # 4. Ensure scripts are executable (chmod +x only, no re-transfer)
        step("ENSURE SCRIPTS EXECUTABLE")
        script_errors = _ensure_scripts_executable(ssh)
        if script_errors:
            print("\n[ERROR] Script chmod errors:")
            for e in script_errors:
                print(f"  - {e}")
            sys.exit(1)

        # 5. Install display dependencies
        step("INSTALL DEPS")
        if not install_display_deps(ssh):
            print("\n[ERROR] Failed to install display dependencies. Aborting.")
            sys.exit(1)

        # 6. Restart backend
        step("RESTART BACKEND")
        restart_status = deploy_svc.restart_backend()
        if not restart_status.success:
            print(f"\n[ERROR] Backend restart failed: {restart_status.message}")
            sys.exit(1)
        print(f"  Backend restart: {restart_status.message}")

        # ── Path-specific post-processing ──

        if args.install_service:
            step("INSTALL SYSTEMD SERVICES")
            svc_status = deploy_svc.install_services()
            if not svc_status.success:
                print(f"\n[ERROR] Service installation failed: {svc_status.message}")
                sys.exit(1)
            print(f"  Service installation: {svc_status.message}")
            print("\n  [DONE] Services installed. Reboot to start HMI on TFT:")
            print(f"    ssh {USER}@{HOST} sudo reboot")
            return

        if args.hmi:
            run_hmi(ssh)
            return

        # Default: verify + optional run
        # Wait for /health/ready (30 intentos, 1s cada uno)
        for i in range(30):
            if check_backend_ready(ssh):
                print(f"  Backend ready after {i+1}s")
                break
            time.sleep(1)
        else:
            print("  [WARN] Backend not ready after 30s")

        # Restart display service
        ssh.execute(
            "sudo systemctl restart rpi-hmi-display.service 2>/dev/null || true",
            timeout=10,
        )
        print("  Display service restarted")

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
