"""
backend.app.services.deploy_service
====================================

Servicio de despliegue remoto sobre SSH.

Utiliza ``SSHDriver`` para escanear la red local en busca de la
Raspberry Pi, configurar el entorno Python, copiar archivos del
proyecto, ejecutar diagnósticos y verificar la salud del backend.

    Uso típico::

        from backend.app.services.ssh_manager import ParamikoSSHDriver
        from backend.app.services.deploy_service import DeployService

        ssh = ParamikoSSHDriver()
        ssh.connect("192.168.1.100", "pi", "password")
        deploy = DeployService(ssh)
        deploy.setup_environment()
        deploy.deploy_app()
        status = deploy.health_check()
"""
from __future__ import annotations

import logging
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict

from backend.app.services.ssh_manager import SSHDriver, SSHResult

logger = logging.getLogger("backend.services.deploy")


# ── Network Scanner ────────────────────────────────────────────────────


@dataclass
class ScanResult:
    """Resultado del escaneo de red para localizar una Raspberry Pi.

    Atributos:
        ip: Dirección IP donde se detectó una Pi.
        hostname: Hostname reportado (puede ser None).
        model: Modelo detectado (desde /proc/device-tree/model).
        ssh_available: True si el puerto 22 responde.
    """

    ip: str
    hostname: Optional[str] = None
    model: Optional[str] = None
    ssh_available: bool = False


class NetworkScanner:
    """Escáner de red local para detectar Raspberry Pi.

    Busca dispositivos con puerto SSH abierto e intenta identificar
    modelos Raspberry Pi mediante comandos remotos.

    No requiere credenciales SSH para la detección básica (solo sondeo TCP),
    pero para identificar el modelo necesita conexión autenticada.
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
            # Fallback: subredes comunes
            subnets = ["192.168.1", "192.168.0", "10.0.0"]
        return subnets or ["192.168.1", "192.168.0", "10.0.0"]

    @staticmethod
    def _check_ssh(ip: str, port: int = 22, timeout: float = 1.0) -> bool:
        """Verifica si un host tiene el puerto SSH abierto.

        Args:
            ip: Dirección IP a sondear.
            port: Puerto TCP (por defecto 22).
            timeout: Timeout en segundos.

        Returns:
            True si el puerto responde.
        """
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
        """Escanea la red local en busca de Raspberry Pi.

        Prueba las IPs .1 a .max_hosts en cada subred local, buscando
        puerto SSH (22) abierto. Las IPs con SSH se reportan como
        posibles Raspberry Pi.

        Args:
            timeout: Timeout en segundos para cada sondeo TCP.
            max_hosts: Número máximo de hosts a sondear por subred.

        Returns:
            Lista de ScanResult con dispositivos detectados.
        """
        results: List[ScanResult] = []
        subnets = NetworkScanner._get_local_subnets()
        logger.info(
            "Escaneando %d subred(es), rango .1-.%d, timeout=%.1fs",
            len(subnets),
            max_hosts,
            timeout,
        )

        for subnet in subnets:
            for i in range(1, max_hosts + 1):
                ip = f"{subnet}.{i}"
                if NetworkScanner._check_ssh(ip, timeout=timeout):
                    logger.info("SSH detectado en %s", ip)
                    # Intentar resolver hostname
                    hostname = None
                    try:
                        hostname = socket.gethostbyaddr(ip)[0]
                    except Exception:
                        pass

                    results.append(ScanResult(ip=ip, hostname=hostname, ssh_available=True))

                    # Si encontramos una, paramos (optimización)
                    if len(results) >= 3:
                        logger.info("Límite de resultados alcanzado, deteniendo escaneo")
                        return results

        if not results:
            logger.warning("No se encontraron dispositivos con SSH en la red local")

        return results

    @staticmethod
    def identify(ip: str, ssh: SSHDriver) -> Optional[ScanResult]:
        """Identifica el modelo de un dispositivo ya detectado vía SSH.

        Args:
            ip: IP del dispositivo.
            ssh: Driver SSH ya conectado al dispositivo.

        Returns:
            ScanResult con el modelo detectado, o None si falla.
        """
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
    """Estado de una operación de despliegue.

    Atributos:
        step: Nombre del paso ejecutado.
        success: True si el paso se completó correctamente.
        message: Descripción del resultado.
        output: Salida de consola relevante (stdout/stderr).
        duration_ms: Duración del paso en milisegundos.
    """

    step: str
    success: bool
    message: str
    output: str = ""
    duration_ms: float = 0.0


class DeployService:
    """Servicio de despliegue remoto para la Raspberry Pi.

    Utiliza un ``SSHDriver`` inyectado para ejecutar todas las operaciones
    de configuración, copia de archivos, diagnóstico y verificación en
    la Raspberry Pi objetivo.

    Atributos:
        ssh: Driver SSH (real o mock) usado para la comunicación.
        remote_root: Ruta raíz del proyecto en la Pi.
        status_log: Historial de pasos ejecutados con su resultado.

    Ejemplo::

        ssh = ParamikoSSHDriver()
        ssh.connect("192.168.1.100", "pi", "password")
        deploy = DeployService(ssh)
        deploy.setup_environment()
        deploy.deploy_app()
        print(deploy.health_check())
    """

    def __init__(self, ssh: SSHDriver, remote_root: str = "/home/pi/Rpi_Pantalla_V1") -> None:
        """Inicializa el servicio de despliegue.

        Args:
            ssh: Driver SSH conectado a la Raspberry Pi.
            remote_root: Directorio raíz del proyecto en la Pi.
        """
        self.ssh = ssh
        self.remote_root = remote_root
        self.status_log: List[DeployStatus] = []
        logger.info("DeployService inicializado — remote_root=%s", remote_root)

    # ── Escaneo ──────────────────────────────────────────────────────

    def detect_raspberry_pi(self, timeout: float = 1.0) -> List[ScanResult]:
        """Escanea la red local en busca de Raspberry Pi.

        Args:
            timeout: Timeout en segundos para cada sondeo TCP.

        Returns:
            Lista de ScanResult con los dispositivos detectados.
        """
        logger.info("Iniciando detección de Raspberry Pi en la red local")
        results = NetworkScanner.scan(timeout=timeout)
        self.status_log.append(DeployStatus(
            step="detect",
            success=len(results) > 0,
            message=f"Encontradas {len(results)} posible(s) Raspberry Pi",
            output="\n".join(r.ip for r in results),
        ))
        return results

    # ── Configuración del entorno ────────────────────────────────────

    def setup_environment(self) -> List[DeployStatus]:
        """Configura el entorno Python en la Raspberry Pi.

        Crea el directorio del proyecto, el entorno virtual (.venv) e
        instala las dependencias desde requirements.txt.

        Pasos ejecutados:
            1. Crear estructura de directorios.
            2. Instalar paquetes del sistema (python3-venv, etc.).
            3. Crear entorno virtual Python.
            4. Instalar dependencias pip.

        Returns:
            Lista de DeployStatus con el resultado de cada paso.
        """
        import time

        steps: List[DeployStatus] = []
        logger.info("Configurando entorno en la Raspberry Pi...")

        # 1. Crear estructura de directorios
        t0 = time.time()
        result = self.ssh.execute(f"mkdir -p {self.remote_root}/backend/app/services "
                                  f"{self.remote_root}/backend/app/api "
                                  f"{self.remote_root}/backend/config "
                                  f"{self.remote_root}/diagnostics/gpio "
                                  f"{self.remote_root}/scripts")
        steps.append(DeployStatus(
            step="mkdir",
            success=result.ok,
            message="Directorios creados" if result.ok else f"Error: {result.stderr}",
            output=result.stderr,
            duration_ms=(time.time() - t0) * 1000,
        ))

        # 2. Verificar/instalar python3-venv
        t0 = time.time()
        result = self.ssh.execute("dpkg -l python3-venv 2>/dev/null | grep -q '^ii' && echo 'OK' || "
                                  "(sudo apt update -qq && sudo apt install -y python3-venv python3-pip python3-dev -qq && echo 'OK')")
        steps.append(DeployStatus(
            step="install_system_deps",
            success=result.ok and "OK" in result.stdout,
            message="Paquetes del sistema verificados/instalados",
            output=result.stdout,
            duration_ms=(time.time() - t0) * 1000,
        ))

        # 3. Crear entorno virtual
        t0 = time.time()
        result = self.ssh.execute(
            f"cd {self.remote_root} && "
            f"if [ ! -d .venv ]; then python3 -m venv .venv && echo 'CREATED'; else echo 'EXISTS'; fi"
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
            f".venv/bin/pip install --upgrade pip -q && "
            f".venv/bin/pip install -r backend/requirements.txt -q 2>&1"
        )
        pip_ok = result.ok and "error" not in result.stderr.lower()
        steps.append(DeployStatus(
            step="pip_install",
            success=pip_ok,
            message="Dependencias instaladas" if pip_ok else f"Error instalando dependencias: {result.stderr[:200]}",
            output=result.stdout + "\n" + result.stderr,
            duration_ms=(time.time() - t0) * 1000,
        ))

        self.status_log.extend(steps)
        return steps

    # ── Despliegue de la aplicación ──────────────────────────────────

    def deploy_app(self, project_root: Optional[str] = None) -> List[DeployStatus]:
        """Copia los archivos del proyecto a la Raspberry Pi.

        Transfiere todos los archivos .py, .yaml y .txt del proyecto
        local al directorio remoto usando SFTP.

        Args:
            project_root: Ruta local del proyecto. Si es None, se usa
                          el directorio de trabajo actual (Path.cwd()).

        Returns:
            Lista de DeployStatus con el resultado de cada archivo.
        """
        import os
        import time

        if project_root is None:
            project_root = str(Path.cwd())

        steps: List[DeployStatus] = []
        logger.info("Desplegando archivos desde %s → %s", project_root, self.remote_root)

        # Archivos a desplegar (local → remoto relativo)
        files_to_deploy = [
            ("backend/app/main.py", "backend/app/main.py"),
            ("backend/app/config.py", "backend/app/config.py"),
            ("backend/app/services/__init__.py", "backend/app/services/__init__.py"),
            ("backend/app/services/ssh_manager.py", "backend/app/services/ssh_manager.py"),
            ("backend/app/services/deploy_service.py", "backend/app/services/deploy_service.py"),
            ("backend/app/api/__init__.py", "backend/app/api/__init__.py"),
            ("backend/app/api/ssh.py", "backend/app/api/ssh.py"),
            ("backend/app/api/deploy.py", "backend/app/api/deploy.py"),
            ("backend/config/devices.yaml", "backend/config/devices.yaml"),
            ("backend/requirements.txt", "backend/requirements.txt"),
            ("diagnostics/run_diagnostics.py", "diagnostics/run_diagnostics.py"),
            ("diagnostics/gpio/blink_test.py", "diagnostics/gpio/blink_test.py"),
        ]

        for local_rel, remote_rel in files_to_deploy:
            local_path = os.path.join(project_root, local_rel)
            remote_path = f"{self.remote_root}/{remote_rel}"

            if not os.path.isfile(local_path):
                logger.warning("Archivo local no encontrado, saltando: %s", local_path)
                steps.append(DeployStatus(
                    step=f"deploy:{local_rel}",
                    success=False,
                    message=f"Archivo local no encontrado: {local_rel}",
                ))
                continue

            t0 = time.time()
            try:
                self.ssh.transfer_file(local_path, remote_path)
                steps.append(DeployStatus(
                    step=f"deploy:{local_rel}",
                    success=True,
                    message=f"Copiado: {local_rel}",
                    duration_ms=(time.time() - t0) * 1000,
                ))
            except Exception as exc:
                logger.exception("Error copiando %s", local_rel)
                steps.append(DeployStatus(
                    step=f"deploy:{local_rel}",
                    success=False,
                    message=f"Error: {exc}",
                    duration_ms=(time.time() - t0) * 1000,
                ))

        self.status_log.extend(steps)
        return steps

    # ── Diagnóstico remoto ───────────────────────────────────────────

    def run_diagnostics(self) -> DeployStatus:
        """Ejecuta el script de diagnóstico en la Raspberry Pi.

        Returns:
            DeployStatus con el resultado completo del diagnóstico.
        """
        import time

        logger.info("Ejecutando diagnóstico remoto...")
        t0 = time.time()
        remote_script = f"{self.remote_root}/diagnostics/run_diagnostics.py"
        result = self.ssh.execute(
            f"cd {self.remote_root} && .venv/bin/python {remote_script} --output {self.remote_root}/diagnostics/report"
        )

        status = DeployStatus(
            step="diagnostics",
            success=result.ok,
            message="Diagnóstico completado" if result.ok else f"Error: {result.stderr[:200]}",
            output=result.stdout + "\n" + result.stderr,
            duration_ms=(time.time() - t0) * 1000,
        )
        self.status_log.append(status)
        return status

    # ── Verificación de salud ────────────────────────────────────────

    def health_check(self, port: int = 8000) -> DeployStatus:
        """Verifica que el backend FastAPI responde en la Pi.

        Realiza una petición HTTP al endpoint /health del backend remoto.

        Args:
            port: Puerto donde escucha el backend remoto.

        Returns:
            DeployStatus indicando si el backend está respondiendo.
        """
        import time

        logger.info("Verificando salud del backend remoto en puerto %d...", port)
        t0 = time.time()

        # Usar curl desde la propia Pi para verificar localhost
        result = self.ssh.execute(
            f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{port}/health 2>/dev/null || echo 'FAIL'"
        )

        is_healthy = result.stdout.strip() == "200"
        status = DeployStatus(
            step="health_check",
            success=is_healthy,
            message="Backend responde correctamente" if is_healthy else f"Backend no responde (código: {result.stdout.strip()})",
            output=result.stdout,
            duration_ms=(time.time() - t0) * 1000,
        )
        self.status_log.append(status)
        return status

    # ── Inicio / parada del backend ──────────────────────────────────

    def start_backend(self, port: int = 8000) -> DeployStatus:
        """Inicia el backend FastAPI en la Raspberry Pi en segundo plano.

        Args:
            port: Puerto donde escuchará el backend.

        Returns:
            DeployStatus con el resultado del inicio.
        """
        import time

        logger.info("Iniciando backend en puerto %d...", port)
        t0 = time.time()

        # Matar instancia previa si existe
        self.ssh.execute("pkill -f 'uvicorn backend.app.main:app' 2>/dev/null || true")

        # Iniciar en segundo plano
        result = self.ssh.execute(
            f"cd {self.remote_root} && "
            f"nohup .venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port {port} "
            f"> /tmp/hmi_backend.log 2>&1 & echo $!"
        )

        pid = result.stdout.strip()
        status = DeployStatus(
            step="start_backend",
            success=result.ok and pid.isdigit(),
            message=f"Backend iniciado (PID: {pid})" if pid.isdigit() else "Error al iniciar backend",
            output=result.stdout,
            duration_ms=(time.time() - t0) * 1000,
        )
        self.status_log.append(status)
        return status

    def stop_backend(self) -> DeployStatus:
        """Detiene el backend FastAPI en la Raspberry Pi.

        Returns:
            DeployStatus con el resultado de la parada.
        """
        import time

        logger.info("Deteniendo backend remoto...")
        t0 = time.time()
        result = self.ssh.execute("pkill -f 'uvicorn backend.app.main:app' 2>/dev/null && echo 'STOPPED' || echo 'NOT_RUNNING'")

        status = DeployStatus(
            step="stop_backend",
            success=True,
            message=result.stdout.strip(),
            output=result.stdout,
            duration_ms=(time.time() - t0) * 1000,
        )
        self.status_log.append(status)
        return status

    # ── Despliegue completo ──────────────────────────────────────────

    def full_deploy(self, project_root: Optional[str] = None) -> Dict[str, List[DeployStatus]]:
        """Ejecuta el ciclo completo de despliegue.

        Pasos:
            1. setup_environment()
            2. deploy_app()
            3. start_backend()
            4. health_check()

        Args:
            project_root: Ruta local del proyecto (None = auto-detectar).

        Returns:
            Diccionario con los resultados agrupados por fase.
        """
        logger.info("=== INICIANDO DESPLIEGUE COMPLETO ===")

        return {
            "environment": self.setup_environment(),
            "deploy": self.deploy_app(project_root),
            "start": [self.start_backend()],
            "health": [self.health_check()],
        }
