"""
backend.app.api.ssh
===================

Endpoints REST para gestionar la conexión SSH con la Raspberry Pi.

Proporciona operaciones para conectar, desconectar, verificar estado
y ejecutar comandos remotos a través del driver SSH inyectado.

    Rutas:
        POST /api/ssh/connect    — Establecer conexión SSH.
        POST /api/ssh/disconnect — Cerrar conexión SSH.
        GET  /api/ssh/status     — Consultar estado de la conexión.
        POST /api/ssh/execute    — Ejecutar un comando remoto.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.services.ssh_manager import SSHDriver, ParamikoSSHDriver, SSHResult

logger = logging.getLogger("backend.api.ssh")

router = APIRouter(prefix="/api/ssh", tags=["SSH"])

# ── Estado global del driver SSH (singleton durante la vida del proceso) ──
_ssh_driver: Optional[SSHDriver] = None


# ── Modelos Pydantic ──────────────────────────────────────────────────────


class SSHConnectRequest(BaseModel):
    """Datos necesarios para establecer una conexión SSH.

    Atributos:
        host: Dirección IP o hostname de la Raspberry Pi.
        user: Nombre de usuario para autenticación SSH.
        password: Contraseña para autenticación (nunca se almacena en logs).
        key_path: Ruta a clave privada SSH (opcional, alternativa a password).
        port: Puerto TCP del servidor SSH (por defecto 22).
        timeout: Timeout de conexión en segundos (por defecto 15).
    """

    host: str = Field(..., description="IP o hostname de la Raspberry Pi", examples=["192.168.1.100"])
    user: str = Field(default="pi", description="Usuario SSH", examples=["pi"])
    password: str = Field(default="", description="Contraseña SSH (no se guarda en logs)")
    key_path: str = Field(default="", description="Ruta a clave privada SSH (opcional)")
    port: int = Field(default=22, ge=1, le=65535, description="Puerto SSH")
    timeout: int = Field(default=15, ge=1, le=60, description="Timeout en segundos")


class SSHExecuteRequest(BaseModel):
    """Comando a ejecutar en el host remoto.

    Atributos:
        command: Comando de shell a ejecutar.
        timeout: Timeout máximo de ejecución en segundos (por defecto 30).
    """

    command: str = Field(..., description="Comando a ejecutar", examples=["uname -a"])
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout en segundos")


class SSHStatusResponse(BaseModel):
    """Estado actual de la conexión SSH.

    Atributos:
        connected: True si hay una conexión activa.
        host: IP del host conectado (None si no hay conexión).
        user: Usuario SSH utilizado (None si no hay conexión).
    """

    connected: bool
    host: Optional[str] = None
    user: Optional[str] = None


class SSHResultResponse(BaseModel):
    """Resultado de la ejecución de un comando remoto.

    Atributos:
        command: Comando que se ejecutó.
        exit_code: Código de salida (0 = éxito).
        stdout: Salida estándar del comando.
        stderr: Salida de error del comando.
        ok: True si exit_code == 0.
    """

    command: str
    exit_code: int
    stdout: str
    stderr: str
    ok: bool


class SSHMessageResponse(BaseModel):
    """Respuesta genérica con mensaje de estado.

    Atributos:
        message: Texto descriptivo del resultado de la operación.
        success: True si la operación se completó correctamente.
    """

    message: str
    success: bool


# ── Dependencia: obtener driver SSH ───────────────────────────────────────


def get_ssh_driver() -> Optional[SSHDriver]:
    """Devuelve el driver SSH global si está conectado.

    Returns:
        El driver SSH activo o None.

    Raises:
        HTTPException 503: Si no hay ningún driver instanciado.
    """
    if _ssh_driver is None:
        raise HTTPException(status_code=503, detail="SSH no configurado. Usa POST /api/ssh/connect primero.")
    return _ssh_driver


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.post("/connect", response_model=SSHMessageResponse)
def ssh_connect(req: SSHConnectRequest) -> SSHMessageResponse:
    """Establece una conexión SSH con la Raspberry Pi.

    Cierra cualquier conexión previa antes de abrir la nueva.
    Las credenciales viajan en el body y no se persisten.
    """
    global _ssh_driver
    logger.info("Solicitud de conexión SSH a %s@%s:%d", req.user, req.host, req.port)

    # Cerrar conexión previa si existe
    if _ssh_driver is not None:
        try:
            _ssh_driver.disconnect()
        except Exception:
            pass

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
        logger.info("Conexión SSH establecida con %s", req.host)
        return SSHMessageResponse(message=f"Conectado a {req.host} como {req.user}", success=True)
    except PermissionError as exc:
        logger.warning("Auth fallida: %s", exc)
        raise HTTPException(status_code=401, detail=str(exc))
    except TimeoutError as exc:
        logger.warning("Timeout: %s", exc)
        raise HTTPException(status_code=504, detail=str(exc))
    except ConnectionError as exc:
        logger.warning("Conexión rechazada: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.exception("Error inesperado conectando SSH")
        raise HTTPException(status_code=500, detail=f"Error interno: {exc}")


@router.post("/disconnect", response_model=SSHMessageResponse)
def ssh_disconnect() -> SSHMessageResponse:
    """Cierra la conexión SSH activa."""
    global _ssh_driver
    if _ssh_driver is not None:
        try:
            _ssh_driver.disconnect()
        except Exception:
            pass
        _ssh_driver = None
        logger.info("Conexión SSH cerrada")
        return SSHMessageResponse(message="Desconectado correctamente", success=True)
    return SSHMessageResponse(message="No había conexión activa", success=True)


@router.get("/status", response_model=SSHStatusResponse)
def ssh_status(driver: Optional[SSHDriver] = Depends(get_ssh_driver)) -> SSHStatusResponse:
    """Devuelve el estado actual de la conexión SSH.

    Incluye si está conectado, y en ese caso, el host y usuario.
    """
    if driver is None or not driver.is_connected():
        return SSHStatusResponse(connected=False)

    # ParamikoSSHDriver almacena host y user como atributos
    host = getattr(driver, "host", "desconocido")
    user = getattr(driver, "user", "desconocido")
    return SSHStatusResponse(connected=True, host=host, user=user)


@router.post("/execute", response_model=SSHResultResponse)
def ssh_execute(
    req: SSHExecuteRequest,
    driver: Optional[SSHDriver] = Depends(get_ssh_driver),
) -> SSHResultResponse:
    """Ejecuta un comando en la Raspberry Pi vía SSH.

    El comando se ejecuta en el host remoto y se devuelve el resultado
    completo (stdout, stderr, exit_code).

    Args:
        req: Comando a ejecutar y timeout opcional.
        driver: Driver SSH inyectado por dependencia.

    Returns:
        SSHResultResponse con el resultado del comando.

    Raises:
        HTTPException 503: Si no hay conexión SSH activa.
    """
    if driver is None:
        raise HTTPException(status_code=503, detail="No hay conexión SSH activa")

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
        raise HTTPException(status_code=504, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Error ejecutando comando remoto")
        raise HTTPException(status_code=500, detail=f"Error: {exc}")
@router.get("/exec", response_model=SSHResultResponse)
def ssh_exec_get(
    cmd: str = Query(..., description="Comando a ejecutar en la Raspberry Pi"),
    driver: Optional[SSHDriver] = Depends(get_ssh_driver),
) -> SSHResultResponse:
    """Ejecuta un comando en la Raspberry Pi vía SSH (método GET).

    Útil para herramientas que solo soportan GET (como fetch_webpage).
    El comando se pasa como query parameter ?cmd=...

    Args:
        cmd: Comando de shell a ejecutar en la Pi.
        driver: Driver SSH inyectado por dependencia.

    Returns:
        SSHResultResponse con el resultado del comando.

    Raises:
        HTTPException 503: Si no hay conexión SSH activa.
    """
    if driver is None:
        raise HTTPException(status_code=503, detail="No hay conexión SSH activa")

    logger.info("Ejecutando comando remoto (GET): %s", cmd[:100])
    try:
        result: SSHResult = driver.execute(cmd, timeout=30)
        return SSHResultResponse(
            command=result.command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            ok=result.ok,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Error ejecutando comando remoto")
        raise HTTPException(status_code=500, detail=f"Error: {exc}")


# ── Auto-conexión al arrancar ──────────────────────────────────────────
import os as _os
from dotenv import load_dotenv as _load_dotenv

_load_dotenv()


_auto_connect_done = False
@router.on_event("startup")
async def _auto_connect_ssh():
    """Conecta automáticamente a la Raspberry Pi al arrancar el backend.

    Lee las credenciales del archivo .env en la raíz del proyecto.
    Si la conexión falla, el backend sigue funcionando (se puede
    conectar manualmente vía POST /api/ssh/connect).
    """
    global _ssh_driver, _auto_connect_done
    if _auto_connect_done:
        logger.info("Auto-conexión SSH ya realizada, omitiendo...")
        return
    _auto_connect_done = True

    rpi_host = _os.getenv("RPI_HOST")
    rpi_user = _os.getenv("RPI_USER", "pi")
    rpi_password = _os.getenv("RPI_PASSWORD", "")
    rpi_key_path = _os.getenv("RPI_KEY_PATH", "")

    if not rpi_host:
        logger.warning("Auto-conexión SSH: falta RPI_HOST en .env")
        return

    if not rpi_password and not rpi_key_path:
        logger.warning("Auto-conexión SSH: falta RPI_PASSWORD o RPI_KEY_PATH en .env")
        return

    try:
        driver = ParamikoSSHDriver()
        driver.connect(
            host=rpi_host,
            user=rpi_user,
            password=rpi_password,
            port=int(_os.getenv("RPI_PORT", "22")),
            timeout=int(_os.getenv("RPI_TIMEOUT", "15")),
            key_path=rpi_key_path,
        )
        _ssh_driver = driver
        logger.info("Auto-conectado SSH a %s@%s", rpi_user, rpi_host)
    except Exception as exc:
        logger.warning("Auto-conexión SSH fallida: %s. Usa POST /api/ssh/connect manualmente.", exc)
