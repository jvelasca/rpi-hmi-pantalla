"""
backend.app.api.ssh
===================

Endpoints REST para gestionar la conexion SSH con la Raspberry Pi.

Proporciona operaciones para conectar, desconectar, verificar estado
y ejecutar comandos remotos a traves del driver SSH inyectado.

    Rutas:
        POST /admin/ssh/connect    — Establecer conexion SSH.
        POST /admin/ssh/disconnect — Cerrar conexion SSH.
        GET  /admin/ssh/status     — Consultar estado de la conexion.
        POST /admin/ssh/execute    — Ejecutar un comando remoto.

TODOS los endpoints requieren autenticacion via header X-API-Key.
"""
from __future__ import annotations

import contextlib
import logging

from dotenv import load_dotenv as _load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.api.deps import require_admin_api_key_always
from backend.app.config import settings
from backend.app.services.ssh_manager import ParamikoSSHDriver, SSHDriver, SSHResult

logger = logging.getLogger("backend.api.ssh")

router = APIRouter(prefix="/admin/ssh", tags=["Admin/SSH"])

# ── Estado global del driver SSH (singleton durante la vida del proceso) ──
_ssh_driver: SSHDriver | None = None

# ── Modelos Pydantic ──────────────────────────────────────────────────────


class SSHConnectRequest(BaseModel):
    """Datos necesarios para establecer una conexion SSH.

    Atributos:
        host: Direccion IP o hostname de la Raspberry Pi.
        user: Nombre de usuario para autenticacion SSH.
        password: Contrasena para autenticacion (nunca se almacena en logs).
        key_path: Ruta a clave privada SSH (opcional, alternativa a password).
        port: Puerto TCP del servidor SSH (por defecto 22).
        timeout: Timeout de conexion en segundos (por defecto 15).
    """

    host: str = Field(..., description="IP o hostname de la Raspberry Pi", examples=["192.168.1.100"])
    user: str = Field(default="pi", description="Usuario SSH", examples=["pi"])
    password: str = Field(default="", description="Contrasena SSH (no se guarda en logs)")
    key_path: str = Field(default="", description="Ruta a clave privada SSH (opcional)")
    port: int = Field(default=22, ge=1, le=65535, description="Puerto SSH")
    timeout: int = Field(default=15, ge=1, le=60, description="Timeout en segundos")


class SSHExecuteRequest(BaseModel):
    """Comando a ejecutar en el host remoto.

    Atributos:
        command: Comando de shell a ejecutar.
        timeout: Timeout maximo de ejecucion en segundos (por defecto 30).
    """

    command: str = Field(..., description="Comando a ejecutar", examples=["uname -a"])
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout en segundos")


class SSHStatusResponse(BaseModel):
    """Estado actual de la conexion SSH.

    Atributos:
        connected: True si hay una conexion activa.
        host: IP del host conectado (None si no hay conexion).
        user: Usuario SSH utilizado (None si no hay conexion).
    """

    connected: bool
    host: str | None = None
    user: str | None = None


class SSHResultResponse(BaseModel):
    """Resultado de la ejecucion de un comando remoto.

    Atributos:
        command: Comando que se ejecuto.
        exit_code: Codigo de salida (0 = exito).
        stdout: Salida estandar del comando.
        stderr: Salida de error del comando.
        ok: True si exit_code == 0.
    """

    command: str
    exit_code: int
    stdout: str
    stderr: str
    ok: bool


class SSHMessageResponse(BaseModel):
    """Respuesta generica con mensaje de estado.

    Atributos:
        message: Texto descriptivo del resultado de la operacion.
        success: True si la operacion se completo correctamente.
    """

    message: str
    success: bool


# ── Dependencia: obtener driver SSH ───────────────────────────────────────


def get_ssh_driver() -> SSHDriver | None:
    """Devuelve el driver SSH global si esta conectado.

    Returns:
        El driver SSH activo o None.

    Raises:
        HTTPException 503: Si no hay ningun driver instanciado.
    """
    if _ssh_driver is None:
        raise HTTPException(
            status_code=503,
            detail="SSH no configurado. Usa POST /admin/ssh/connect primero.",
        )
    return _ssh_driver


# ── Endpoints ─────────────────────────────────────────────────────────────

# Todos los endpoints requieren API key


@router.post(
    "/connect",
    response_model=SSHMessageResponse,
    dependencies=[Depends(require_admin_api_key_always)],
)
def ssh_connect(req: SSHConnectRequest) -> SSHMessageResponse:
    """Establece una conexion SSH con la Raspberry Pi.

    Cierra cualquier conexion previa antes de abrir la nueva.
    Las credenciales viajan en el body y no se persisten.
    Requiere autenticacion: header X-API-Key.
    """
    global _ssh_driver
    logger.info("Solicitud de conexion SSH a %s@%s:%d", req.user, req.host, req.port)

    # Cerrar conexion previa si existe
    if _ssh_driver is not None:
        with contextlib.suppress(Exception):
            _ssh_driver.disconnect()

    driver = ParamikoSSHDriver()
    try:
        driver.connect(
            host=req.host,
            user=req.user,
            password=req.password,
            port=req.port,
            timeout=req.timeout,
            key_path=req.key_path,
        )
        _ssh_driver = driver
        logger.info("Conexion SSH establecida con %s", req.host)
        return SSHMessageResponse(message=f"Conectado a {req.host} como {req.user}", success=True)
    except PermissionError as exc:
        logger.warning("Auth fallida: %s", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except TimeoutError as exc:
        logger.warning("Timeout: %s", exc)
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except ConnectionError as exc:
        logger.warning("Conexion rechazada: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error inesperado conectando SSH")
        raise HTTPException(status_code=500, detail=f"Error interno: {exc}") from exc


@router.post(
    "/disconnect",
    response_model=SSHMessageResponse,
    dependencies=[Depends(require_admin_api_key_always)],
)
def ssh_disconnect() -> SSHMessageResponse:
    """Cierra la conexion SSH activa. Requiere autenticacion."""
    global _ssh_driver
    if _ssh_driver is not None:
        with contextlib.suppress(Exception):
            _ssh_driver.disconnect()
        _ssh_driver = None
        logger.info("Conexion SSH cerrada")
        return SSHMessageResponse(message="Desconectado correctamente", success=True)
    return SSHMessageResponse(message="No habia conexion activa", success=True)


@router.get(
    "/status",
    response_model=SSHStatusResponse,
    dependencies=[Depends(require_admin_api_key_always)],
)
def ssh_status(driver: SSHDriver | None = Depends(get_ssh_driver)) -> SSHStatusResponse:  # noqa: B008
    """Devuelve el estado actual de la conexion SSH. Requiere autenticacion.

    Incluye si esta conectado, y en ese caso, el host y usuario.
    """
    if driver is None or not driver.is_connected():
        return SSHStatusResponse(connected=False)

    host = getattr(driver, "host", "desconocido")
    user = getattr(driver, "user", "desconocido")
    return SSHStatusResponse(connected=True, host=host, user=user)


@router.post(
    "/execute",
    response_model=SSHResultResponse,
    dependencies=[Depends(require_admin_api_key_always)],
)
def ssh_execute(
    req: SSHExecuteRequest,
    driver: SSHDriver | None = Depends(get_ssh_driver),  # noqa: B008
) -> SSHResultResponse:
    """Ejecuta un comando en la Raspberry Pi via SSH. Requiere autenticacion.

    El comando se ejecuta en el host remoto y se devuelve el resultado
    completo (stdout, stderr, exit_code).

    Args:
        req: Comando a ejecutar y timeout opcional.
        driver: Driver SSH inyectado por dependencia.

    Returns:
        SSHResultResponse con el resultado del comando.

    Raises:
        HTTPException 503: Si no hay conexion SSH activa.
    """
    if driver is None:
        raise HTTPException(status_code=503, detail="No hay conexion SSH activa")

    logger.info("Ejecutando comando remoto: %s", req.command[:100])
    try:
        result: SSHResult = driver.execute(req.command, timeout=req.timeout)
        return SSHResultResponse(
            command=result.command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            ok=result.ok,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Error ejecutando comando remoto")
        raise HTTPException(status_code=500, detail=f"Error: {exc}") from exc


# ── Auto-conexion al arrancar (solo si hay configuracion) ─────────────────

_load_dotenv()

_auto_connect_done = False


async def auto_connect_ssh() -> None:
    """Conecta automaticamente a la Raspberry Pi al arrancar el backend.

    Lee las credenciales del archivo .env en la raiz del proyecto.
    Si la conexion falla, el backend sigue funcionando (se puede
    conectar manualmente via POST /admin/ssh/connect).

    Se llama desde el lifespan del app en main.py en lugar
    de usar el deprecated router.on_event('startup').
    """
    global _ssh_driver, _auto_connect_done
    if _auto_connect_done:
        logger.info("Auto-conexion SSH ya realizada, omitiendo...")
        return
    _auto_connect_done = True

    if not settings.rpi_host:
        logger.info("Auto-conexion SSH: no configurada (RPI_HOST vacio)")
        return

    if not settings.rpi_password and not settings.rpi_key_path:
        logger.info("Auto-conexion SSH: no configurada (sin password ni clave)")
        return

    try:
        driver = ParamikoSSHDriver()
        driver.connect(
            host=settings.rpi_host,
            user=settings.rpi_user,
            password=settings.rpi_password,
            port=settings.rpi_port,
            timeout=settings.rpi_timeout,
            key_path=settings.rpi_key_path,
        )
        _ssh_driver = driver
        logger.info("Auto-conectado SSH a %s@%s", settings.rpi_user, settings.rpi_host)
    except Exception as exc:
        logger.warning("Auto-conexion SSH fallida: %s. Usa POST /admin/ssh/connect manualmente.", exc)
