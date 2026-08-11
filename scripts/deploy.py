"""Deploy + verify display app to Raspberry Pi in one shot.

Usage:
    python scripts/deploy.py                     # deploy + verify
    python scripts/deploy.py --run               # deploy + run display app (solo Pi!)
    python scripts/deploy.py --hmi               # deploy, stop lightdm, run HMI en TFT
    python scripts/deploy.py --verify            # solo verificar estado
    python scripts/deploy.py --install-service   # instalar systemd services (arranque automatico)
"""

import argparse
import sys
import time
from pathlib import Path

import paramiko

HOST = "192.168.88.211"
USER = "pi"
PASSWORD = "RaspberryB+2026!"
PORT = 22
PI_BASE = "/home/pi/rpi_hmi"
VENV_PY = f"{PI_BASE}/venv/bin/python3"
ROOT = Path(__file__).resolve().parents[1]
DISPLAY_DIR = ROOT / "display"
SCRIPTS_DIR = ROOT / "scripts"
CONFIG_DIR = ROOT / "config"


def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=15)
    return c


def sh(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("ascii", "replace").strip()
    err = stderr.read().decode("ascii", "replace").strip()
    code = stdout.channel.recv_exit_status()
    return code, out, err


def step(msg):
    print(f"\n{'='*55}\n  {msg}\n{'='*55}")


def deploy(client):
    """Sync display/ files to Pi via SFTP."""
    sftp = client.open_sftp()
    # Ensure dirs
    for d in ["display", "display/ui", "display/tests"]:
        try:
            sftp.mkdir(f"{PI_BASE}/{d}")
        except IOError:
            pass

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
            try:
                sftp.stat(parent)
            except FileNotFoundError:
                sftp.mkdir(parent)
            local_time = py_file.stat().st_mtime
            try:
                remote_time = sftp.stat(remote).st_mtime
                if local_time <= remote_time:
                    continue  # Skip unchanged
            except FileNotFoundError:
                pass
            sftp.put(str(py_file), remote)
            size = py_file.stat().st_size
            print(f"  OK  {rel} ({size}B)")
            count += 1
        except Exception as exc:
            print(f"  ERR {rel}: {exc}")
    sftp.close()
    print(f"  Total: {count} files synced")
    return count


def deploy_scripts(client):
    """Sync scripts/ to Pi (start_hmi.sh, etc.)."""
    sftp = client.open_sftp()
    try:
        sftp.mkdir(f"{PI_BASE}/scripts")
    except IOError:
        pass

    for script_file in SCRIPTS_DIR.glob("*"):
        if script_file.name.endswith(".pyc") or script_file.name == "__pycache__":
            continue
        rel = str(script_file.relative_to(ROOT)).replace("\\", "/")
        remote = f"{PI_BASE}/{rel}"
        sftp.put(str(script_file), remote)
        # Make .sh files executable
        if script_file.suffix == ".sh":
            sh(client, f"chmod +x {remote}")
            print(f"  OK  {rel} (chmod +x)")
        else:
            print(f"  OK  {rel} ({script_file.stat().st_size}B)")
    sftp.close()


def install_deps(client):
    """Install missing Python packages in venv."""
    needed = []
    for mod in ["pygame", "evdev", "requests", "websocket"]:
        code, out, err = sh(client, f"{VENV_PY} -c 'import {mod}' 2>&1")
        if code != 0:
            needed.append(mod)

    if needed:
        print(f"  Installing: {', '.join(needed)}")
        code, out, err = sh(client,
            f"source {PI_BASE}/venv/bin/activate && pip install {' '.join(needed)} 2>&1 | tail -3",
            timeout=300
        )
        print(f"  pip exit={code}")
    else:
        print("  All deps already installed")

    # Verify
    verify_cmd = (
        f"{VENV_PY} -c 'import pygame,evdev,requests,websocket; "
        "print(f\"pygame={pygame.version.ver}, evdev OK, "
        "req={requests.__version__}, ws={websocket.__version__}\")' 2>&1"
    )
    code, out, err = sh(client, verify_cmd)
    print(f"  [verify] {out}")
    if err:
        print(f"  [stderr] {err[:100]}")


def verify(client):
    """Run verification checks."""
    # Health
    code, out, err = sh(client, "curl -s http://localhost:8000/health")
    print(f"  Backend health: {out}")

    # Display devices
    code, out, err = sh(client, "ls -la /dev/dri/card0 /dev/fb1 /dev/input/event0 2>&1")
    print(f"  Devices:\n{out}")

    # Check if lightdm is running
    code, out, err = sh(client, "systemctl is-active lightdm 2>&1 || echo 'inactive'")
    print(f"  lightdm: {out.strip()}")

    # Check DRM card0 users
    code, out, err = sh(client, "sudo fuser /dev/dri/card0 2>/dev/null | xargs ps -p 2>/dev/null | tail -3 || echo 'free'")
    print(f"  DRM card0 users:\n{out}")

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
    code, out, err = sh(client, cmd, timeout=15)
    print(f"  Import chain: {'OK' if 'ALL IMPORTS OK' in out else 'FAIL'}")
    if err:
        print(f"  [stderr] {err[:200]}")


def ensure_backend(client):
    """Start backend if not running."""
    code, out, err = sh(client, "curl -s http://localhost:8000/health")
    if code == 0 and "ok" in out:
        print("  Backend already running")
        return
    print("  Starting backend...")
    sh(client,
        f"cd {PI_BASE} && PYTHONPATH={PI_BASE} nohup {VENV_PY} "
        f"-m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 "
        f"> /tmp/backend.log 2>&1 &"
    )
    time.sleep(2)
    code, out, err = sh(client, "curl -s http://localhost:8000/health")
    print(f"  Backend start: {'OK' if code == 0 else 'FAIL'} - {out}")


def stop_lightdm(client):
    """Stop lightdm to free /dev/dri/card0."""
    code, out, err = sh(client, "systemctl is-active lightdm 2>&1 || echo 'inactive'")
    if "active" not in out:
        print("  lightdm already stopped")
        return True

    print("  Stopping lightdm...")
    code, out, err = sh(client, "sudo systemctl stop lightdm", timeout=10)
    time.sleep(2)

    # Verify card0 is free
    code, out, err = sh(client, "sudo fuser /dev/dri/card0 2>/dev/null || echo 'free'")
    if "free" in out:
        print("  lightdm stopped, /dev/dri/card0 liberated")
        return True
    else:
        print(f"  [WARN] /dev/dri/card0 still in use by: {out}")
        # Try force kill
        sh(client, "sudo fuser -k /dev/dri/card0 2>/dev/null || true")
        time.sleep(1)
        return True


def unbind_console(client):
    """Unbind vtcon1 from fb1 (ili9486)."""
    code, out, err = sh(client,
        "test -w /sys/class/vtconsole/vtcon1/bind && "
        "echo 0 | sudo tee /sys/class/vtconsole/vtcon1/bind > /dev/null 2>&1 && "
        "echo 'vtcon1 unbound' || echo 'vtcon1 not available'"
    )
    print(f"  Console: {out.strip()}")


def ensure_video_group(client):
    """Add pi user to video group if needed."""
    code, out, err = sh(client, "groups pi | grep -q video && echo 'yes' || echo 'no'")
    if "yes" in out:
        print("  pi already in video group")
        return
    print("  Adding pi to video group...")
    sh(client, "sudo usermod -a -G video pi")
    print("  Done. May need to logout/login for group to take effect.")


def run_hmi(client):
    """Run HMI app on Pi display (DRM/KMS)."""
    step("RUN HMI ON TFT DISPLAY")
    stop_lightdm(client)
    unbind_console(client)
    ensure_video_group(client)

    print("\n  Launching display/app.py on Pi TFT (ili9486)...")
    print("  Press Ctrl+C to stop.\n")

    cmd = (
        f"cd {PI_BASE} && "
        f"SDL_VIDEODRIVER=kmsdrm SDL_KMSDRM_DEVICE_INDEX=0 "
        f"PYTHONPATH={PI_BASE} PYTHONUNBUFFERED=1 "
        f"{VENV_PY} -m display.app --api-url http://localhost:8000 --debug"
    )
    stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)

    try:
        while True:
            chunk = stdout.channel.recv(1024)
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    except KeyboardInterrupt:
        print("\n  Stopped by user")
        # Send Ctrl+C to remote process
        stdin.channel.send(b'\x03')


def install_services(client):
    """Install systemd services on Pi (backend + display)."""
    sftp = client.open_sftp()

    # Create systemd dir (recursive)
    for d in ["config", "config/systemd"]:
        try:
            sftp.mkdir(f"{PI_BASE}/{d}")
        except IOError:
            pass

    for svc_file in (CONFIG_DIR / "systemd").glob("*.service"):
        rel = str(svc_file.relative_to(ROOT)).replace("\\", "/")
        remote = f"{PI_BASE}/{rel}"
        sftp.put(str(svc_file), remote)
        print(f"  Uploaded {svc_file.name}")

        svc_name = svc_file.name
        target = f"/etc/systemd/system/{svc_name}"

        # Copy to systemd
        code, out, err = sh(client, f"sudo cp {remote} {target}")
        print(f"  Installed {target}")

    sftp.close()

    # Reload systemd
    sh(client, "sudo systemctl daemon-reload")
    print("  systemd daemon-reload done")

    # Enable services
    for svc_file in (CONFIG_DIR / "systemd").glob("*.service"):
        svc_name = svc_file.name
        code, out, err = sh(client, f"sudo systemctl enable {svc_name}")
        print(f"  Enable {svc_name}: {out.strip()}")

    # Disable lightdm so it doesn't conflict
    code, out, err = sh(client, "sudo systemctl disable lightdm 2>&1 || echo 'already'")
    print(f"  Disable lightdm: {out.strip()}")

    print("\n  [DONE] Services installed. Reboot to start HMI on TFT:")
    print(f"    ssh pi@{HOST} sudo reboot")


def main():
    p = argparse.ArgumentParser(description="RPi HMI deploy script")
    p.add_argument("--run", action="store_true", help="Run display app on Pi (requires console)")
    p.add_argument("--hmi", action="store_true", help="Stop lightdm, run HMI on Pi TFT display")
    p.add_argument("--verify", action="store_true", help="Only verify, no deploy")
    p.add_argument("--install-service", action="store_true", help="Install systemd services + disable lightdm")
    args = p.parse_args()

    client = ssh()
    print("[OK] Connected to", HOST)

    if args.verify:
        step("VERIFICATION")
        verify(client)
        client.close()
        return

    if args.install_service:
        deploy(client)
        deploy_scripts(client)
        install_deps(client)
        step("INSTALL SYSTEMD SERVICES")
        install_services(client)
        client.close()
        return

    if args.hmi:
        deploy(client)
        deploy_scripts(client)
        install_deps(client)
        run_hmi(client)
        client.close()
        return

    # Default: deploy + verify
    step("ENSURE BACKEND")
    ensure_backend(client)

    step("DEPLOY FILES")
    deploy(client)
    deploy_scripts(client)

    step("INSTALL DEPS")
    install_deps(client)

    step("VERIFY")
    verify(client)

    if args.run:
        step("RUN DISPLAY APP (Ctrl+C to stop)")
        print("  Running display/app.py on Pi...")
        cmd = (
            f"cd {PI_BASE} && PYTHONPATH={PI_BASE} {VENV_PY} display/app.py"
        )
        stdin, stdout, stderr = client.exec_command(cmd, get_pty=True)
        try:
            while True:
                chunk = stdout.channel.recv(1024)
                if not chunk:
                    break
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
        except KeyboardInterrupt:
            print("\n  Stopped by user")

    client.close()
    print("\n[DONE]")


if __name__ == "__main__":
    main()
