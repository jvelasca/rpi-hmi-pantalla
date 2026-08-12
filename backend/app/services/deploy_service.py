"""
backend.app.services.deploy_service
====================================

Servicio de despliegue remoto sobre SSH.

Utiliza ``SSHDriver`` para escanear la red local en busca de la
Raspberry Pi, configurar el entorno Python, sincronizar archivos del
proyecto completo, ejecutar diagnosticos y verificar la salud del backend.

La ruta de despliegue esta unificada en REMOTE_ROOT y la gestion
de servicios se hace via systemctl (nada de nohup/pkill).

    Uso tipico::

        from backend.app.services.ssh_manager import ParamikoSSHDriver
        from backend.app.services.deploy_service import DeployService

        ssh = ParamikoSSHDriver()
        ssh.connect("192.168.1.100", "pi", "password")
        deploy = DeployService(ssh)
        deploy.setup_environment()
        deploy.deploy_app()
        deploy.restart_backend()
        status = deploy.health_check()
"""
from __future__ import annotations

import logging
import os
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict

from backend.app.services.ssh_manager import SSHDriver, SSHResult

logger = logging.getLogger("backend.services.deploy")

# ── Constantes unificadas ────────────────────────────────────────────────
REMOTE_ROOT = "/home/pi/rpi_hmi"
VENV_PYTHON = f"{REMOTE_ROOT}/venv/bin/python3"
VENV_PIP = f"{REMOTE_ROOT}/venv/bin/pip"

# Directorios que deben desplegarse completos (todos los .py, .yaml, .txt, .json, .toml)
DEPLOY_DIRECTORIES = [
    "backend/app",
    "backend/config",
    "backend/tests",
    "display",
    "config/systemd",
    "scripts",
    "frontend/dist",
    "diagnostics",
]

# Archivos raiz individuales que deben copiarse
DEPLOY_ROOT_FILES = [
    "backend/pyproject.toml",
    "backend/requirements.txt",
    "backend/__init__.py",
    "VERSION",
]


# ── Network Scanner ────────────────────────────────────────────────────


@dataclass
class ScanResult:
    """Resultado del escaneo de red para localizar una Raspberry Pi.

    Atributos:
        ip: Direccion IP donde se detecto una Pi.
        hostname: Hostname reportado (puede ser None).
        model: Modelo detectado (desde /proc/device-tree/model).
        ssh_available: True si el puerto 22 responde.
    """

    ip: str
    hostname: Optional[str] = None
    model: Optional[str] = None
    ssh_available: bool = False


class NetworkScanner:
    """Escanner de red local para detectar Raspberry Pi.

    Busca dispositivos con puerto SSH abierto e intenta identificar
    modelos Raspberry Pi mediante comandos remotos.

    No requiere credenciales SSH para la deteccion basica (solo sondeo TCP),
    pero para identificar el modelo necesita conexion autenticada.
    """

    @staticmethod
    def _get_local_subnets() -> List[str]:
        """Obtiene las subredes locales de las interfaces de red activas.

        Returns:
            Lista de prefijos de subred en formato '192.168.1'.
        """
        subnets: List[str] = []
        try:
            hostname = socket.gethostname()
            ips = socket.gethostbyname_ex(hostname)[2]
            for ip in ips:
                if ip.startswith("127."):
                    continue
                parts = ip.rsplit(".", 1)
                if len(parts) == 2:
                    subnets.append(parts[0])
        except Exception:
            subnets = ["192.168.1", "192.168.0", "10.0.0"]
        return subnets or ["192.168.1", "192.168.0", "10.0.0"]

    @staticmethod
    def _check_ssh(ip: str, port: int = 22, timeout: float = 1.0) -> bool:
        """Verifica si un host tiene el puerto SSH abierto."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    @staticmethod
    def scan(timeout: float = 1.0, max_hosts: int = 20) -> List[ScanResult]:
        """Escanea la red local en busca de Raspberry Pi."""
        results: List[ScanResult] = []
        subnets = NetworkScanner._get_local_subnets()
        logger.info(
            "Escaneando %d subred(es), rango .1-.%d, timeout=%.1fs",
            len(subnets), max_hosts, timeout,
        )

        for subnet in subnets:
            for i in range(1, max_hosts + 1):
                ip = f"{subnet}.{i}"
                if NetworkScanner._check_ssh(ip, timeout=timeout):
                    logger.info("SSH detectado en %s", ip)
                    hostname = None
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                    except Exception:
                        pass
                    results.append(ScanResult(ip=ip, hostname=hostname, ssh_available=True))
                    if len(results) >= 3:
                        logger.info("Limite de resultados alcanzado, deteniendo escaneo")
                        return results

        if not results:
            logger.warning("No se encontraron dispositivos con SSH en la red local")
        return results

    @staticmethod
    def identify(ip: str, ssh: SSHDriver) -> Optional[ScanResult]:
        """Identifica el modelo de un dispositivo ya detectado via SSH."""
        try:
            model_result = ssh.execute("cat /proc/device-tree/model 2>/dev/null || echo 'unknown'")
            model = model_result.stdout.strip() if model_result.ok else None
            hostname_result = ssh.execute("hostname")
            hostname = hostname_result.stdout.strip() if hostname_result.ok else None
            return ScanResult(ip=ip, hostname=hostname, model=model, ssh_available=True)
        except Exception as exc:
            logger.warning("No se pudo identificar %s: %s", ip, exc)
            return ScanResult(ip=ip, ssh_available=True)


# ── Deploy Service ─────────────────────────────────────────────────────


@dataclass
class DeployStatus:
    """Estado de una operacion de despliegue."""

    step: str
    success: bool
    message: str
    output: str = ""
    duration_ms: float = 0.0


class DeployService:
    """Servicio de despliegue remoto para la Raspberry Pi.

    Utiliza un ``SSHDriver`` inyectado para ejecutar todas las operaciones
    de configuracion, copia de archivos, diagnostico y verificacion en
    la Raspberry Pi objetivo.

    La gestion del backend se hace via systemctl, no via nohup/pkill.

    Atributos:
        ssh: Driver SSH (real o mock) usado para la comunicacion.
        remote_root: Ruta raiz del proyecto en la Pi (/home/pi/rpi_hmi).
        status_log: Historial de pasos ejecutados con su resultado.
    """

    def __init__(self, ssh: SSHDriver, remote_root: str = REMOTE_ROOT) -> None:
        """Inicializa el servicio de despliegue.

        Args:
            ssh: Driver SSH conectado a la Raspberry Pi.
            remote_root: Directorio raiz del proyecto en la Pi.
        """
        self.ssh = ssh
        self.remote_root = remote_root
        self.status_log: List[DeployStatus] = []
        logger.info("DeployService inicializado — remote_root=%s", remote_root)

    # ── Escaneo ──────────────────────────────────────────────────────

    def detect_raspberry_pi(self, timeout: float = 1.0) -> List[ScanResult]:
        """Escanea la red local en busca de Raspberry Pi."""
        logger.info("Iniciando deteccion de Raspberry Pi en la red local")
        results = NetworkScanner.scan(timeout=timeout)
        self.status_log.append(DeployStatus(
            step="detect",
            success=len(results) > 0,
            message=f"Encontradas {len(results)} posible(s) Raspberry Pi",
            output="\n".join(r.ip for r in results),
        ))
        return results

    # ── Configuracion del entorno ────────────────────────────────────

    def setup_environment(self) -> List[DeployStatus]:
        """Configura el entorno Python en la Raspberry Pi.

        Crea el directorio del proyecto, el entorno virtual (venv/) e
        instala las dependencias desde requirements.txt.

        NOTA: Usa venv/ (no .venv) para consistencia con systemd.
        """
        import time

        steps: List[DeployStatus] = []
        logger.info("Configurando entorno en la Raspberry Pi...")

        # 1. Crear estructura de directorios
        t0 = time.time()
        result = self.ssh.execute(
            f"mkdir -p {self.remote_root}"
            f" {self.remote_root}/backend/app/services"
            f" {self.remote_root}/backend/app/api"
            f" {self.remote_root}/backend/app/models"
            f" {self.remote_root}/backend/app/hardware"
            f" {self.remote_root}/backend/config"
            f" {self.remote_root}/backend/tests"
            f" {self.remote_root}/display/ui"
            f" {self.remote_root}/display/tests"
            f" {self.remote_root}/config/systemd"
            f" {self.remote_root}/scripts"
            f" {self.remote_root}/data"
        )
        steps.append(DeployStatus(
            step="mkdir",
            success=result.ok,
            message="Directorios creados" if result.ok else f"Error: {result.stderr}",
            output=result.stderr,
            duration_ms=(time.time() - t0) * 1000,
        ))

        # 2. Verificar/instalar python3-venv
        t0 = time.time()
        result = self.ssh.execute(
            "dpkg -l python3-venv 2>/dev/null | grep -q '^ii' && echo 'OK' || "
            "(sudo apt update -qq && sudo apt install -y python3-venv python3-pip python3-dev -qq && echo 'OK')"
        )
        steps.append(DeployStatus(
            step="install_system_deps",
            success=result.ok and "OK" in result.stdout,
            message="Paquetes del sistema verificados/instalados",
            output=result.stdout,
            duration_ms=(time.time() - t0) * 1000,
        ))

        # 3. Crear entorno virtual (venv/ para consistencia con systemd)
        t0 = time.time()
        result = self.ssh.execute(
            f"cd {self.remote_root} && "
            f"if [ ! -d venv ]; then python3 -m venv venv && echo 'CREATED'; else echo 'EXISTS'; fi"
        )
        steps.append(DeployStatus(
            step="create_venv",
            success=result.ok,
            message=f"Entorno virtual: {result.stdout.strip()}",
            output=result.stdout,
            duration_ms=(time.time() - t0) * 1000,
        ))

        # 4. Instalar dependencias pip
        t0 = time.time()
        result = self.ssh.execute(
            f"cd {self.remote_root} && "
            f"{VENV_PIP} install --upgrade pip -q && "
            f"{VENV_PIP} install -r backend/requirements.txt -q 2>&1"
        )
        pip_ok = result.ok and "error" not in result.stderr.lower()
        steps.append(DeployStatus(
            step="pip_install",
            success=pip_ok,
            message="Dependencias instaladas" if pip_ok else f"Error: {result.stderr[:200]}",
            output=result.stdout + "\n" + result.stderr,
            duration_ms=(time.time() - t0) * 1000,
        ))

        self.status_log.extend(steps)
        return steps

    # ── Despliegue de la aplicacion ──────────────────────────────────

    def deploy_app(self, project_root: Optional[str] = None) -> List[DeployStatus]:
        """Copia el proyecto completo a la Raspberry Pi via SFTP.

        Despliega directorios completos (con sus archivos .py, .yaml, .toml)
        en lugar de una lista manual de archivos. Esto garantiza que el
        despliegue siempre coincida con el codigo en Git.

        Args:
            project_root: Ruta local del proyecto. Si es None, se usa
                          el directorio de trabajo actual.

        Returns:
            Lista de DeployStatus con el resultado de cada archivo.
        """
        import time

        if project_root is None:
            project_root = str(Path.cwd())

        steps: List[DeployStatus] = []
        logger.info("Desplegando proyecto desde %s -> %s", project_root, self.remote_root)

        # Limpiar frontend/dist remoto antes de copiar para evitar
        # que assets antiguos de builds anteriores queden residuales
        self.ssh.execute(
            f"rm -rf {self.remote_root}/frontend/dist && mkdir -p {self.remote_root}/frontend/dist",
            timeout=10,
        )

        # Desplegar directorios completos (solo .py, .yaml, .json, .toml, .txt, .sh)
        allowed_extensions = {".py", ".yaml", ".yml", ".json", ".toml", ".txt", ".sh", ".service",
                              ".js", ".css", ".html", ".svg", ".ico", ".woff2"}

        for dir_rel in DEPLOY_DIRECTORIES:
            local_dir = Path(project_root) / dir_rel
            if not local_dir.is_dir():
                logger.warning("Directorio local no encontrado, saltando: %s", dir_rel)
                continue

            for local_file in local_dir.rglob("*"):
                if local_file.is_dir():
                    continue
                if "__pycache__" in local_file.parts:
                    continue
                if local_file.suffix == ".pyc":
                    continue
                if local_file.suffix not in allowed_extensions and local_file.suffix:
                    continue

                rel = str(local_file.relative_to(project_root)).replace("\\", "/")
                remote = f"{self.remote_root}/{rel}"

                # Ensure remote directory exists
                remote_dir = str(Path(remote).parent)
                self.ssh.execute(f"mkdir -p {remote_dir}", timeout=10)

                t0 = time.time()
                try:
                    self.ssh.transfer_file(str(local_file), remote)
                    steps.append(DeployStatus(
                        step=f"deploy:{rel}",
                        success=True,
                        message=f"Copiado: {rel}",
                        duration_ms=(time.time() - t0) * 1000,
                    ))
                except Exception as exc:
                    logger.exception("Error copiando %s", rel)
                    steps.append(DeployStatus(
                        step=f"deploy:{rel}",
                        success=False,
                        message=f"Error: {exc}",
                        duration_ms=(time.time() - t0) * 1000,
                    ))

        # Archivos raiz individuales
        for root_file_rel in DEPLOY_ROOT_FILES:
            local_path = Path(project_root) / root_file_rel
            if not local_path.is_file():
                continue
            remote = f"{self.remote_root}/{root_file_rel}"
            remote_dir = str(Path(remote).parent)
            self.ssh.execute(f"mkdir -p {remote_dir}", timeout=10)

            t0 = time.time()
            try:
                self.ssh.transfer_file(str(local_path), remote)
                steps.append(DeployStatus(
                    step=f"deploy:{root_file_rel}",
                    success=True,
                    message=f"Copiado: {root_file_rel}",
                    duration_ms=(time.time() - t0) * 1000,
                ))
            except Exception as exc:
                steps.append(DeployStatus(
                    step=f"deploy:{root_file_rel}",
                    success=False,
                    message=f"Error: {exc}",
                    duration_ms=(time.time() - t0) * 1000,
                ))

        logger.info("Despliegue completado: %d archivos copiados", len(steps))
        self.status_log.extend(steps)
        return steps

    # ── Diagnostico remoto ───────────────────────────────────────────

    def run_diagnostics(self) -> DeployStatus:
        """Ejecuta el script de diagnostico en la Raspberry Pi."""
        import time

        logger.info("Ejecutando diagnostico remoto...")
        t0 = time.time()
        remote_script = f"{self.remote_root}/diagnostics/run_diagnostics.py"
        result = self.ssh.execute(
            f"cd {self.remote_root} && {VENV_PYTHON} {remote_script} "
            f"--output {self.remote_root}/diagnostics/report"
        )

        status = DeployStatus(
            step="diagnostics",
            success=result.ok,
            message="Diagnostico completado" if result.ok else f"Error: {result.stderr[:200]}",
            output=result.stdout + "\n" + result.stderr,
            duration_ms=(time.time() - t0) * 1000,
        )
        self.status_log.append(status)
        return status

    # ── Verificacion de salud ────────────────────────────────────────

    def health_check(self, port: int = 8000) -> DeployStatus:
        """Verifica que el backend FastAPI responde en la Pi.

        Usa /health/ready (solo codigo HTTP, no grep de texto).

        Args:
            port: Puerto donde escucha el backend remoto.

        Returns:
            DeployStatus indicando si el backend esta respondiendo.
        """
        import time

        logger.info("Verificando salud del backend remoto en puerto %d...", port)
        t0 = time.time()

        # Usar curl con -fsS: fail on error, silent, show errors
        # /health/ready devuelve 200 si listo, 503 si no
        result = self.ssh.execute(
            f"curl -fsS -o /dev/null -w '%{{http_code}}' "
            f"http://localhost:{port}/health/ready 2>/dev/null || echo 'FAIL'"
        )

        is_healthy = result.stdout.strip() == "200"
        status = DeployStatus(
            step="health_check",
            success=is_healthy,
            message="Backend responde correctamente" if is_healthy
            else f"Backend no responde (codigo: {result.stdout.strip()})",
            output=result.stdout,
            duration_ms=(time.time() - t0) * 1000,
        )
        self.status_log.append(status)
        return status

    # ── Gestion del backend via systemctl ───────────────────────────

    def start_backend(self) -> DeployStatus:
        """Inicia el backend via systemctl.

        En lugar de nohup/pkill, usa el servicio systemd instalado.
        """
        import time

        logger.info("Iniciando backend via systemctl...")
        t0 = time.time()

        result = self.ssh.execute(
            "sudo systemctl start rpi-hmi-backend.service 2>&1 && echo 'STARTED' || echo 'FAILED'",
            timeout=30,
        )

        ok = "STARTED" in result.stdout
        status = DeployStatus(
            step="start_backend",
            success=ok,
            message="Backend iniciado via systemctl" if ok
            else f"Error: {result.stderr[:200]}",
            output=result.stdout,
            duration_ms=(time.time() - t0) * 1000,
        )
        self.status_log.append(status)
        return status

    def stop_backend(self) -> DeployStatus:
        """Detiene el backend via systemctl."""
        import time

        logger.info("Deteniendo backend via systemctl...")
        t0 = time.time()

        result = self.ssh.execute(
            "sudo systemctl stop rpi-hmi-backend.service 2>&1 && echo 'STOPPED' || echo 'NOT_RUNNING'",
            timeout=30,
        )

        status = DeployStatus(
            step="stop_backend",
            success=True,
            message=result.stdout.strip(),
            output=result.stdout,
            duration_ms=(time.time() - t0) * 1000,
        )
        self.status_log.append(status)
        return status

    def restart_backend(self) -> DeployStatus:
        """Reinicia el backend via systemctl.

        Este es el metodo preferido para aplicar cambios tras un deploy.
        """
        import time

        logger.info("Reiniciando backend via systemctl...")
        t0 = time.time()

        result = self.ssh.execute(
            "sudo systemctl restart rpi-hmi-backend.service 2>&1 && echo 'RESTARTED' || echo 'FAILED'",
            timeout=30,
        )

        ok = "RESTARTED" in result.stdout
        status = DeployStatus(
            step="restart_backend",
            success=ok,
            message="Backend reiniciado via systemctl" if ok
            else f"Error: {result.stderr[:200]}",
            output=result.stdout,
            duration_ms=(time.time() - t0) * 1000,
        )
        self.status_log.append(status)
        return status

    def install_services(self) -> DeployStatus:
        """Instala y habilita los servicios systemd en la Pi."""
        import time

        logger.info("Instalando servicios systemd...")
        t0 = time.time()

        # Copiar archivos .service a /etc/systemd/system/
        svc_dir = f"{self.remote_root}/config/systemd"
        result = self.ssh.execute(
            f"sudo cp {svc_dir}/rpi-hmi-backend.service /etc/systemd/system/ && "
            f"sudo cp {svc_dir}/rpi-hmi-display.service /etc/systemd/system/ && "
            f"sudo systemctl daemon-reload && "
            f"sudo systemctl enable rpi-hmi-backend.service rpi-hmi-display.service && "
            f"sudo systemctl disable lightdm 2>/dev/null || true && "
            f"echo 'INSTALLED'",
            timeout=30,
        )

        ok = "INSTALLED" in result.stdout
        status = DeployStatus(
            step="install_services",
            success=ok,
            message="Servicios systemd instalados y habilitados" if ok
            else f"Error: {result.stderr[:200]}",
            output=result.stdout,
            duration_ms=(time.time() - t0) * 1000,
        )
        self.status_log.append(status)
        return status

    # ── Despliegue completo ──────────────────────────────────────────

    def full_deploy(self, project_root: Optional[str] = None) -> Dict[str, List[DeployStatus]]:
        """Ejecuta el ciclo completo de despliegue con fail-fast.

        Si un paso falla, no continua con los siguientes.

        Args:
            project_root: Ruta local del proyecto (None = auto-detectar).

        Returns:
            Diccionario con los resultados agrupados por fase.
        """
        logger.info("=== INICIANDO DESPLIEGUE COMPLETO ===")
        results: Dict[str, List[DeployStatus]] = {}

        # 1. Environment
        env_steps = self.setup_environment()
        results["environment"] = env_steps
        if any(not s.success for s in env_steps):
            logger.error("Fase environment fallida, abortando deploy")
            return results

        # 2. Deploy
        deploy_steps = self.deploy_app(project_root)
        results["deploy"] = deploy_steps
        if any(not s.success for s in deploy_steps):
            logger.error("Fase deploy fallida, abortando deploy")
            return results

        # 3. Services
        service_status = self.install_services()
        results["services"] = [service_status]
        if not service_status.success:
            logger.error("Fase services fallida, abortando deploy")
            return results

        # 4. Restart
        restart_status = self.restart_backend()
        results["restart"] = [restart_status]
        if not restart_status.success:
            logger.error("Fase restart fallida, abortando deploy")
            return results

        # 5. Health
        health_status = self.health_check()
        results["health"] = [health_status]

        return results
