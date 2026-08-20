"""Atomic deploy with releases/ directory and current symlink.

Arquitectura en la Pi:
    /home/pi/rpi_hmi/
    ├── releases/
    │   ├── 0.3.0/
    │   └── 0.3.1/
    ├── current -> releases/0.3.1
    └── data/

Flujo del deploy atomico:
    1. Leer VERSION del proyecto local
    2. Conectar SSH
    3. Crear directorio releases/{VERSION}/ en la Pi
    4. Copiar TODOS los archivos del proyecto a releases/{VERSION}/ (NO a current)
    5. Si algun archivo falla -> abortar (no tocar current)
    6. Validar que la estructura es correcta
    7. setup_environment() en el nuevo release
    8. ln -sfn releases/{VERSION} current
    9. restart_backend() + esperar /health/ready
    10. restart_display()
    11. verify()

Rollback:
    1. Leer releases disponibles
    2. ln -sfn releases/{VERSION_ANTERIOR} current
    3. restart

Usage:
    python scripts/deploy_atomic.py                    # Deploy current version
    python scripts/deploy_atomic.py --rollback          # Rollback to previous version
    python scripts/deploy_atomic.py --list              # List installed versions
    python scripts/deploy_atomic.py --version 0.3.1     # Deploy specific version
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Cargar .env desde raiz del proyecto
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Imports tras load_dotenv(): los modulos de backend leen settings del entorno al importar.
from backend.app.services.deploy_service import DeployService  # noqa: E402
from backend.app.services.ssh_manager import ParamikoSSHDriver  # noqa: E402

HOST = os.getenv("RPI_HOST", "")
USER = os.getenv("RPI_USER", "pi")
PASSWORD = os.getenv("RPI_PASSWORD", "")
KEY_PATH = os.getenv("RPI_KEY_PATH", "")
PORT = int(os.getenv("RPI_PORT", "22"))

if not HOST:
    sys.exit("ERROR: RPI_HOST no configurado. Establece RPI_HOST en .env")

# ── Paths ──────────────────────────────────────────────────────
PI_BASE = "/home/pi/rpi_hmi"
RELEASES_DIR = f"{PI_BASE}/releases"
CURRENT_LINK = f"{PI_BASE}/current"
VENV_PY = f"{PI_BASE}/venv/bin/python3"
ROOT = Path(__file__).resolve().parents[1]

# Regex semver estricto
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def connect_ssh() -> ParamikoSSHDriver:
    """Crea y conecta un SSHDriver usando credenciales del entorno."""
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


def read_local_version() -> str:
    """Lee la version desde el archivo VERSION en la raiz del proyecto."""
    version_path = ROOT / "VERSION"
    if not version_path.is_file():
        sys.exit("ERROR: VERSION file not found in project root")
    version = version_path.read_text(encoding="utf-8").strip()
    if not SEMVER_RE.match(version):
        sys.exit(f"ERROR: VERSION '{version}' is not valid semver (X.Y.Z)")
    return version


def check_backend_ready(ssh: ParamikoSSHDriver) -> bool:
    """Verifica que el backend esta listo usando /health/ready (HTTP status)."""
    result = ssh.execute(
        "curl -fsS -o /dev/null -w '%{http_code}' "
        "http://localhost:8000/health/ready 2>/dev/null || echo 'FAIL'",
        timeout=10,
    )
    return result.ok and result.stdout.strip() == "200"


def _check_deploy_steps(steps, label="Deploy"):
    """Verifica que todos los pasos de deploy fueron exitosos."""
    failed = [s for s in steps if not s.success]
    if failed:
        print(f"\n[ERROR] {label}: {len(failed)} archivo(s) no se copiaron:")
        for f in failed:
            print(f"  - {f.step}: {f.message}")
        sys.exit(1)


def deploy_files_to_release(ssh: ParamikoSSHDriver, version: str) -> Path:
    """Copia todos los archivos del proyecto a releases/{version}/ via SFTP.

    Si cualquier archivo falla, aborta sin modificar el symlink current.

    Returns:
        Ruta local temporal (Path) para limpieza posterior.
    """
    release_remote = f"{RELEASES_DIR}/{version}"

    # Crear estructura base en el release
    ssh.execute(f"mkdir -p {release_remote}", timeout=10)

    allowed_extensions = {
        ".py", ".yaml", ".yml", ".json", ".toml", ".txt", ".sh", ".service",
        ".js", ".css", ".html", ".svg", ".ico", ".woff2",
    }
    # Extensiones que deben copiarse SIEMPRE (sin extension, como VERSION)
    no_ext_files = {"VERSION", "README.md", "LICENSE"}

    total = 0
    failed = 0

    for local_file in sorted(ROOT.rglob("*")):
        if local_file.is_dir():
            continue
        if "__pycache__" in local_file.parts:
            continue
        if local_file.suffix == ".pyc":
            continue
        if local_file.name.startswith(".") and local_file.name not in no_ext_files:
            continue
        # Excluir .env y archivos sensibles
        if local_file.name == ".env":
            continue
        # Excluir node_modules y .venv completos
        if "node_modules" in local_file.parts or ".venv" in local_file.parts:
            continue
        # Excluir archivos de datos locales
        if "data" in local_file.parts and local_file.suffix in {".db", ".sqlite", ".sqlite3"}:
            continue

        if local_file.suffix not in allowed_extensions and local_file.name not in no_ext_files:
            continue

        rel = str(local_file.relative_to(ROOT)).replace("\\", "/")
        remote = f"{release_remote}/{rel}"

        # Asegurar directorio remoto
        remote_dir = str(Path(remote).parent)
        ssh.execute(f"mkdir -p {remote_dir}", timeout=10)

        try:
            ssh.transfer_file(str(local_file), remote)
            size = local_file.stat().st_size
            print(f"  OK  {rel} ({size}B)")
            total += 1
        except Exception as exc:
            print(f"  ERR {rel}: {exc}")
            failed += 1

    print(f"  Total: {total} files, {failed} errors")

    if failed > 0:
        # Abortar: limpiar release fallido
        print(f"\n[ABORT] {failed} archivos fallaron. Limpiando release {version}...")
        ssh.execute(f"rm -rf {release_remote}", timeout=30)
        sys.exit(1)

    return Path(release_remote)


def validate_release_structure(ssh: ParamikoSSHDriver, version: str) -> bool:
    """Valida que la estructura del release es correcta."""
    release = f"{RELEASES_DIR}/{version}"
    required = [
        f"{release}/VERSION",
        f"{release}/backend/app/main.py",
        f"{release}/backend/config/devices.yaml",
        f"{release}/display/app.py",
    ]

    missing = []
    for path in required:
        result = ssh.execute(f"test -f {path} && echo 'OK' || echo 'MISSING'", timeout=10)
        if "OK" not in result.stdout:
            missing.append(path)

    if missing:
        print(f"  [FAIL] Faltan archivos requeridos en release {version}:")
        for m in missing:
            print(f"    - {m}")
        return False

    print(f"  [OK] Estructura del release {version} validada")
    return True


def setup_environment_in_release(ssh: ParamikoSSHDriver, version: str) -> None:
    """Instala dependencias pip en el venv del proyecto.

    NOTA: El venv es compartido (PI_BASE/venv) ya que es un deploy atómico
    del mismo proyecto. Solo instalamos deps actualizadas.
    """
    release = f"{RELEASES_DIR}/{version}"
    print(f"  Instalando dependencias desde {release}/backend/requirements.txt...")
    result = ssh.execute(
        f"{VENV_PY} -m pip install --upgrade pip -q && "
        f"{VENV_PY} -m pip install -r {release}/backend/requirements.txt -q 2>&1 | tail -5",
        timeout=300,
    )
    print(f"  pip exit={result.exit_code}")
    if result.stdout.strip():
        print(f"  {result.stdout.strip()}")


def switch_current(ssh: ParamikoSSHDriver, version: str) -> None:
    """Actualiza el symlink current para apuntar al nuevo release."""
    ssh.execute(f"ln -sfn releases/{version} {CURRENT_LINK}", timeout=10)
    print(f"  current -> releases/{version}")


def restart_display(ssh: ParamikoSSHDriver) -> None:
    """Reinicia el servicio display via systemctl."""
    ssh.execute(
        "sudo systemctl restart rpi-hmi-display.service 2>/dev/null || true",
        timeout=10,
    )
    print("  Display service restarted")


def verify_deployed(ssh: ParamikoSSHDriver) -> None:
    """Verifica el estado tras el deploy."""
    result = ssh.execute(
        "curl -fsS http://localhost:8000/health 2>/dev/null || echo 'UNREACHABLE'", timeout=10
    )
    print(f"  Backend health: {result.stdout[:200]}")

    if check_backend_ready(ssh):
        print("  Ready: YES")
    else:
        print("  Ready: NO")

    # Verificar symlink current
    result = ssh.execute(f"readlink {CURRENT_LINK} 2>/dev/null || echo 'NONE'", timeout=10)
    print(f"  current -> {result.stdout.strip()}")

    # Listar releases
    result = ssh.execute(f"ls -1 {RELEASES_DIR}/ 2>/dev/null || echo 'NONE'", timeout=10)
    lines = result.stdout.strip().split("\n")
    print(f"  Releases ({len(lines)}): {', '.join(lines)}")


# ── Rollback ───────────────────────────────────────────────────


def list_releases(ssh: ParamikoSSHDriver) -> list[str]:
    """Lista las versiones instaladas en releases/, ordenadas alfabeticamente."""
    result = ssh.execute(f"ls -1 {RELEASES_DIR}/ 2>/dev/null || echo ''", timeout=10)
    releases = [r for r in result.stdout.strip().split("\n") if r]
    releases.sort()
    return releases


def do_rollback(ssh: ParamikoSSHDriver) -> None:
    """Hace rollback al release anterior."""
    releases = list_releases(ssh)
    if len(releases) < 2:
        print("[ABORT] No hay suficientes releases para hacer rollback (minimo 2)")
        return

    # Obtener version actual
    result = ssh.execute(f"readlink {CURRENT_LINK} 2>/dev/null || echo ''", timeout=10)
    current_target = result.stdout.strip()
    current_version = current_target.split("/")[-1] if "/" in current_target else ""

    # Versión anterior (penultima en la lista ordenada)
    previous = releases[-2] if current_version == releases[-1] else releases[-1]

    step(f"ROLLBACK: {current_version or '?'} -> {previous}")
    switch_current(ssh, previous)

    # Restart
    deploy_svc = DeployService(ssh, remote_root=PI_BASE)
    deploy_svc.restart_backend()
    for i in range(30):
        if check_backend_ready(ssh):
            print(f"  Backend ready after {i+1}s")
            break
        time.sleep(1)
    else:
        print("  [WARN] Backend not ready after 30s")

    restart_display(ssh)
    step("VERIFY AFTER ROLLBACK")
    verify_deployed(ssh)


# ── Main ───────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(
        description="Atomic deploy with releases/ directory and current symlink",
    )
    p.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback to previous version",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="List installed versions on the Pi",
    )
    p.add_argument(
        "--version",
        type=str,
        default=None,
        help="Deploy a specific version (overrides VERSION file, e.g. 0.3.1)",
    )
    args = p.parse_args()

    ssh = connect_ssh()
    try:
        if args.list:
            step("INSTALLED RELEASES")
            releases = list_releases(ssh)
            if releases:
                for r in releases:
                    marker = ""
                    result = ssh.execute(f"readlink {CURRENT_LINK}", timeout=10)
                    if result.stdout.strip().endswith(r):
                        marker = " <-- current"
                    print(f"  {r}{marker}")
            else:
                print("  No releases found")
            return

        if args.rollback:
            do_rollback(ssh)
            return

        # ── Deploy atómico ──────────────────────────────────
        version = args.version or read_local_version()
        if not SEMVER_RE.match(version):
            sys.exit(f"ERROR: '{version}' is not valid semver (X.Y.Z)")

        step(f"ATOMIC DEPLOY — version {version}")

        # Verificar si ya existe ese release
        releases = list_releases(ssh)
        if version in releases:
            print(f"  [WARN] Release {version} ya existe en la Pi. Se sobrescribira.")

        # 1. Crear release y copiar archivos
        step("COPY FILES TO RELEASE")
        deploy_files_to_release(ssh, version)

        # 2. Validar estructura
        step("VALIDATE STRUCTURE")
        if not validate_release_structure(ssh, version):
            sys.exit(1)

        # 3. Setup environment
        step("SETUP ENVIRONMENT")
        setup_environment_in_release(ssh, version)

        # 4. Cambiar symlink (operacion atomica)
        step("SWITCH CURRENT SYMLINK")
        switch_current(ssh, version)

        # 5. Restart backend + esperar ready
        step("RESTART BACKEND")
        deploy_svc = DeployService(ssh, remote_root=PI_BASE)
        deploy_svc.restart_backend()
        for i in range(30):
            if check_backend_ready(ssh):
                print(f"  Backend ready after {i+1}s")
                break
            time.sleep(1)
        else:
            print("  [WARN] Backend not ready after 30s")

        # 6. Restart display
        step("RESTART DISPLAY")
        restart_display(ssh)

        # 7. Verify
        step("VERIFY")
        verify_deployed(ssh)

        # Limpiar releases antiguos (conservar los 3 últimos)
        releases = list_releases(ssh)
        if len(releases) > 3:
            to_remove = releases[:-3]
            print(f"\n  Limpiando {len(to_remove)} release(s) antiguo(s): {to_remove}")
            for old in to_remove:
                ssh.execute(f"rm -rf {RELEASES_DIR}/{old}", timeout=30)
                print(f"    Eliminado: {old}")

    finally:
        ssh.disconnect()

    print(f"\n[DONE] Deploy atomico v{version} completado")


if __name__ == "__main__":
    main()
