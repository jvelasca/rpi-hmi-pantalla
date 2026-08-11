"""
backend.app.services.ssh_manager
=================================

Capa de abstracción para conexiones SSH.

Siguiendo el patrón HAL del proyecto, se define una interfaz abstracta
``SSHDriver`` con dos implementaciones:

- ``ParamikoSSHDriver`` — conexión real vía paramiko (uso en producción).
- ``MockSSHDriver`` — simulador para desarrollo y testing sin hardware.

Incluye soporte para context manager (``with``), manejo de errores
(timeout, auth fallida, conexión perdida) y logging estructurado.

    Uso típico::

        from backend.app.services.ssh_manager import ParamikoSSHDriver

        with ParamikoSSHDriver("192.168.1.100", "pi", "password") as ssh:
            result = ssh.execute("uname -a")
            print(result.stdout)
"""
from __future__ import annotations

import logging
import socket
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("backend.services.ssh")


@dataclass
class SSHResult:
    """Resultado de la ejecución de un comando remoto.

    Atributos:
        stdout: Salida estándar del comando.
        stderr: Salida de error del comando.
        exit_code: Código de salida del proceso remoto (0 = éxito).
        command: Comando ejecutado (para auditoría/traza).
    """

    stdout: str
    stderr: str
    exit_code: int
    command: str

    @property
    def ok(self) -> bool:
        """True si el comando se ejecutó sin errores (exit_code == 0)."""
        return self.exit_code == 0

    def __str__(self) -> str:
        """Representación legible del resultado."""
        parts = [f"[exit={self.exit_code}] {self.command}"]
        if self.stdout:
            parts.append(f"stdout: {self.stdout[:500]}")
        if self.stderr:
            parts.append(f"stderr: {self.stderr[:500]}")
        return "\n".join(parts)


class SSHDriver(ABC):
    """Interfaz abstracta para conexiones SSH.

    Implementaciones concretas:
        - ``ParamikoSSHDriver`` — conexión real con paramiko.
        - ``MockSSHDriver`` — simulación para desarrollo/testing.

    Todas las operaciones remotas deben pasar por esta interfaz para
    garantizar la testabilidad offline y el desacoplamiento del hardware.
    """

    @abstractmethod
    def connect(
        self,
        host: str,
        user: str,
        password: str = "",
        port: int = 22,
        timeout: int = 15,
        key_path: str = "",
    ) -> None:
        """Establece la conexión SSH con el host remoto.

        Args:
            host: Dirección IP o hostname del servidor SSH.
            user: Nombre de usuario para autenticación.
            password: Contraseña para autenticación (opcional si se usa key_path).
            port: Puerto TCP del servidor SSH (por defecto 22).
            timeout: Timeout en segundos para la conexión.
            key_path: Ruta a clave privada SSH (opcional).

        Raises:
            ConnectionError: Si el host no es alcanzable.
            PermissionError: Si las credenciales son incorrectas.
            TimeoutError: Si la conexión excede el timeout.
        """
        ...

    @abstractmethod
    def execute(self, command: str, timeout: int = 30) -> SSHResult:
        """Ejecuta un comando en el host remoto y devuelve el resultado.

        Args:
            command: Comando de shell a ejecutar en el host remoto.
            timeout: Timeout en segundos para la ejecución del comando.

        Returns:
            SSHResult con stdout, stderr, exit_code y el comando ejecutado.

        Raises:
            RuntimeError: Si no hay conexión activa.
            TimeoutError: Si el comando excede el timeout.
        """
        ...

    @abstractmethod
    def transfer_file(self, local_path: str, remote_path: str) -> None:
        """Transfiere un archivo local al host remoto vía SFTP.

        Args:
            local_path: Ruta absoluta del archivo local a transferir.
            remote_path: Ruta absoluta de destino en el host remoto.

        Raises:
            FileNotFoundError: Si el archivo local no existe.
            RuntimeError: Si no hay conexión activa o falla la transferencia.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Cierra la conexión SSH y libera recursos.

        Es seguro llamar a este método múltiples veces (idempotente).
        """
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Devuelve True si la conexión SSH está activa y responde.

        Returns:
            True si la sesión SSH está establecida y el host responde.
        """
        ...

    # ── Context manager ────────────────────────────────────────────

    def __enter__(self) -> SSHDriver:
        """Soporte para 'with SSHDriver(...) as ssh:'."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cierra la conexión automáticamente al salir del bloque with."""
        self.disconnect()
        return None  # No suprime excepciones


class ParamikoSSHDriver(SSHDriver):
    """Implementación real de SSH usando la librería paramiko.

    Proporciona conexión SSH autenticada por contraseña, ejecución remota
    de comandos y transferencia de archivos vía SFTP.

    Atributos:
        host: Dirección IP o hostname del servidor SSH.
        user: Usuario SSH.
        _client: Cliente SSH de paramiko (None si no conectado).
        _sftp: Cliente SFTP asociado (None si no conectado).

    Ejemplo::

        ssh = ParamikoSSHDriver()
        ssh.connect("192.168.1.100", "pi", password="your_password")
        result = ssh.execute("uname -a")
        print(result.stdout)
        ssh.disconnect()
    """

    def __init__(self) -> None:
        """Inicializa el driver sin conexión activa."""
        self.host: str = ""
        self.user: str = ""
        self._client: Optional[object] = None  # paramiko.SSHClient
        self._sftp: Optional[object] = None

    def connect(
        self,
        host: str,
        user: str,
        password: str = "",
        port: int = 22,
        timeout: int = 15,
        key_path: str = "",
    ) -> None:
        """Establece la conexión SSH usando paramiko.

        Soporta autenticación por contraseña y por clave privada.
        Si se proporciona key_path, se usa autenticación por clave.
        En caso contrario, se usa password.

        Args:
            host: IP o hostname del servidor SSH.
            user: Usuario para autenticación.
            password: Contraseña para autenticación (opcional si se usa key_path).
            port: Puerto TCP (por defecto 22).
            timeout: Timeout de conexión en segundos.
            key_path: Ruta a clave privada SSH (opcional).

        Raises:
            ConnectionError: Host inalcanzable o puerto cerrado.
            PermissionError: Credenciales incorrectas.
            TimeoutError: Timeout agotado durante la conexión.
        """
        import os as _os
        import paramiko

        self.host = host
        self.user = user
        auth_method = "clave" if key_path else "password"
        logger.info("Conectando a %s@%s:%d (timeout=%ds, auth=%s)", user, host, port, timeout, auth_method)

        try:
            self._client = paramiko.SSHClient()
            # WarningPolicy: acepta la clave pero advierte. En red local es aceptable.
            # Para entornos con requisitos estrictos, usar RejectPolicy + known_hosts.
            self._client.set_missing_host_key_policy(paramiko.WarningPolicy())
            logger.info("Politica SSH: WarningPolicy (se advierte si la host key es desconocida)")

            connect_kwargs = {
                "hostname": host,
                "port": port,
                "username": user,
                "timeout": timeout,
                "banner_timeout": timeout,
                "auth_timeout": timeout,
            }

            if key_path:
                expanded_path = _os.path.expanduser(key_path)
                if not _os.path.isfile(expanded_path):
                    raise FileNotFoundError(f"Clave privada no encontrada: {expanded_path}")

                # Intentar con diferentes formatos de clave
                key = None
                for key_class in [paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey]:
                    try:
                        key = key_class.from_private_key_file(expanded_path)
                        break
                    except paramiko.SSHException:
                        continue

                if key is None:
                    # Intentar con password de la clave (frase de paso)
                    try:
                        key = paramiko.RSAKey.from_private_key_file(expanded_path, password=password or None)
                    except paramiko.SSHException:
                        pass

                if key is None:
                    raise PermissionError(f"No se pudo leer la clave privada: {expanded_path}")

                connect_kwargs["pkey"] = key
                logger.info("Usando clave privada: %s", expanded_path)
            else:
                connect_kwargs["password"] = password

            self._client.connect(**connect_kwargs)
            self._sftp = self._client.open_sftp()
            logger.info("Conexión SSH establecida con %s", host)
        except paramiko.AuthenticationException as exc:
            logger.error("Autenticación fallida para %s@%s", user, host)
            raise PermissionError(f"Credenciales incorrectas para {user}@{host}") from exc
        except (socket.timeout, paramiko.SSHException) as exc:
            logger.error("Timeout conectando a %s:%d", host, port)
            raise TimeoutError(f"Timeout conectando a {host}:{port} ({timeout}s)") from exc
        except (OSError, EOFError) as exc:
            logger.error("No se pudo conectar a %s:%d — %s", host, port, exc)
            raise ConnectionError(f"No se pudo conectar a {host}:{port}: {exc}") from exc

    def execute(self, command: str, timeout: int = 30) -> SSHResult:
        """Ejecuta un comando en el host remoto vía SSH.

        Args:
            command: Comando de shell a ejecutar.
            timeout: Timeout máximo de ejecución en segundos.

        Returns:
            SSHResult con stdout, stderr y exit_code.

        Raises:
            RuntimeError: Si no hay conexión activa.
            TimeoutError: Si el comando no termina dentro del timeout.
        """
        if not self._client:
            raise RuntimeError("No hay conexión SSH activa. Llama a connect() primero.")

        logger.debug("Ejecutando en %s: %s", self.host, command)
        try:
            _stdin, stdout, stderr = self._client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            stdout_str = stdout.read().decode("utf-8", errors="replace").strip()
            stderr_str = stderr.read().decode("utf-8", errors="replace").strip()

            result = SSHResult(
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=exit_code,
                command=command,
            )
            logger.info(
                "Comando remoto [exit=%d]: %s → stdout=%d bytes, stderr=%d bytes",
                exit_code,
                command[:80],
                len(stdout_str),
                len(stderr_str),
            )
            return result
        except socket.timeout as exc:
            logger.error("Timeout ejecutando comando en %s: %s", self.host, command)
            raise TimeoutError(f"Timeout ejecutando '{command}' (>{timeout}s)") from exc

    def transfer_file(self, local_path: str, remote_path: str) -> None:
        """Transfiere un archivo local al host remoto vía SFTP.

        Args:
            local_path: Ruta absoluta del archivo local.
            remote_path: Ruta absoluta de destino en el host remoto.

        Raises:
            FileNotFoundError: Si el archivo local no existe.
            RuntimeError: Si no hay conexión SFTP activa.
        """
        import os

        if not os.path.isfile(local_path):
            raise FileNotFoundError(f"Archivo local no encontrado: {local_path}")

        if not self._sftp:
            raise RuntimeError("No hay conexión SFTP activa. Llama a connect() primero.")

        logger.info("Transfiriendo %s → %s:%s", local_path, self.host, remote_path)
        # Asegurar que el directorio remoto existe
        remote_dir = "/".join(remote_path.replace("\\", "/").split("/")[:-1])
        if remote_dir:
            try:
                self._sftp.stat(remote_dir)
            except FileNotFoundError:
                # Crear directorio recursivamente
                self.execute(f"mkdir -p {remote_dir}")

        self._sftp.put(local_path, remote_path)
        logger.info("Transferencia completada: %s", remote_path)

    def disconnect(self) -> None:
        """Cierra la conexión SSH y libera recursos.

        Es idempotente: llamar múltiples veces no produce errores.
        """
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None

        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

        logger.info("Conexión SSH cerrada (host=%s)", self.host or "desconocido")

    def is_connected(self) -> bool:
        """Verifica si la conexión SSH está activa.

        Returns:
            True si el cliente SSH está instanciado y la sesión de transporte
            está activa.
        """
        if not self._client:
            return False
        transport = self._client.get_transport()
        return transport is not None and transport.is_active()


class MockSSHDriver(SSHDriver):
    """Driver SSH simulado para desarrollo y testing sin acceso a red.

    Simula una Raspberry Pi remota manteniendo un diccionario de archivos
    virtuales y un historial de comandos ejecutados. No realiza ninguna
    conexión real de red.

    Atributos:
        files: Diccionario ruta_remota → contenido (simula SFTP).
        command_history: Lista de comandos ejecutados (para verificación en tests).
        _connected: Estado de la conexión simulada.
    """

    def __init__(self) -> None:
        """Inicializa el driver mock con estado vacío."""
        self.host: str = ""
        self.user: str = ""
        self.files: dict[str, str] = {}
        self.command_history: list[str] = []
        self._connected: bool = False
        logger.info("MockSSHDriver inicializado")

    def connect(
        self,
        host: str,
        user: str,
        password: str = "",
        port: int = 22,
        timeout: int = 15,
        key_path: str = "",
    ) -> None:
        """Simula la conexión SSH almacenando los parámetros.

        Args:
            host: IP simulada.
            user: Usuario simulado.
            password: Contraseña (no verificada en mock).
            port: Puerto (no verificado).
            timeout: Timeout (no aplica en mock).
            key_path: Ruta de clave (no verificada en mock).

        Raises:
            ConnectionError: Si host es 'fail' (para test de errores).
        """
        if host == "fail":
            raise ConnectionError(f"Mock: conexión rechazada a {host}")

        self.host = host
        self.user = user
        self._connected = True
        logger.info("MockSSHDriver conectado a %s@%s", user, host)

    def execute(self, command: str, timeout: int = 30) -> SSHResult:
        """Simula la ejecución de un comando remoto.

        Comandos especiales para testing:
            - 'fail': Simula fallo (exit_code=1).
            - 'timeout': Simula timeout.
            - 'uname -a': Devuelve info de sistema Raspberry Pi simulada.
            - 'hostname -I': Devuelve IP simulada.
            - 'cat /proc/device-tree/model': Devuelve modelo de Pi.

        Args:
            command: Comando simulado a ejecutar.
            timeout: Timeout simulado (no aplica).

        Returns:
            SSHResult con salida simulada.

        Raises:
            RuntimeError: Si no hay conexión activa.
            TimeoutError: Si el comando es 'timeout'.
        """
        if not self._connected:
            raise RuntimeError("Mock: no hay conexión SSH activa")

        self.command_history.append(command)
        logger.debug("Mock ejecutando: %s", command)

        if command == "fail":
            return SSHResult(stdout="", stderr="Mock: comando fallido", exit_code=1, command=command)
        if command == "timeout":
            raise TimeoutError(f"Mock: timeout ejecutando '{command}'")

        # Respuestas simuladas para comandos comunes
        if "uname -a" in command:
            out = "Linux raspberrypi 6.1.21+ #1642 Mon Apr  3 17:19:14 BST 2023 armv6l GNU/Linux"
        elif "hostname -I" in command or "hostname -i" in command:
            out = self.host or "192.168.1.100"
        elif "cat /proc/device-tree/model" in command:
            out = "Raspberry Pi Model B+ Rev 1.2"
        elif "python3 --version" in command:
            out = "Python 3.9.2"
        elif "echo" in command:
            out = command.replace("echo ", "").strip()
        else:
            out = f"Mock: ejecutado '{command}'"

        return SSHResult(stdout=out, stderr="", exit_code=0, command=command)

    def transfer_file(self, local_path: str, remote_path: str) -> None:
        """Simula la transferencia de un archivo vía SFTP.

        Lee el archivo local (debe existir) y lo almacena en el diccionario
        virtual ``files`` del mock.

        Args:
            local_path: Ruta absoluta del archivo local.
            remote_path: Ruta simulada de destino.

        Raises:
            FileNotFoundError: Si el archivo local no existe.
        """
        import os

        if not os.path.isfile(local_path):
            raise FileNotFoundError(f"Mock: archivo local no encontrado: {local_path}")

        with open(local_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()

        self.files[remote_path] = content
        logger.info("Mock: transferido %s → %s (%d bytes)", local_path, remote_path, len(content))

    def disconnect(self) -> None:
        """Simula la desconexión SSH."""
        self._connected = False
        logger.info("MockSSHDriver desconectado de %s", self.host or "desconocido")

    def is_connected(self) -> bool:
        """Devuelve el estado de la conexión simulada.

        Returns:
            True si connect() fue llamado y disconnect() aún no.
        """
        return self._connected
