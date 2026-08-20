"""
backend.app.api.deploy
======================

Endpoints REST para el despliegue remoto de la aplicacion en la Pi.

Proporciona operaciones para escanear la red, configurar el entorno,
desplegar archivos, ejecutar diagnosticos y verificar salud del backend.

    Rutas:
        POST /admin/deploy/setup       — Configurar entorno Python en la Pi.
        POST /admin/deploy/app         — Desplegar archivos de la aplicacion.
        GET  /admin/deploy/diagnostics — Ejecutar diagnostico remoto.
        GET  /admin/deploy/health      — Verificar salud del backend remoto.
        POST /admin/deploy/start       — Iniciar backend remoto.
        POST /admin/deploy/stop        — Detener backend remoto.
        GET  /admin/deploy/scan        — Escanear red local en busca de Pi.

TODOS los endpoints requieren autenticacion via header X-API-Key.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.api.deps import require_admin_api_key_always
from backend.app.services.deploy_service import DeployService, ScanResult
from backend.app.services.ssh_manager import SSHDriver

logger = logging.getLogger("backend.api.deploy")

router = APIRouter(prefix="/admin/deploy", tags=["Admin/Deploy"])


# ── Dependencia: obtener driver SSH del modulo ssh ────────────────────────


def get_ssh_driver() -> SSHDriver:
    """Obtiene el driver SSH global desde el modulo ssh.

    Returns:
        El driver SSH activo.

    Raises:
        HTTPException 503: Si no hay conexion SSH establecida.
    """
    from backend.app.api.ssh import _ssh_driver

    if _ssh_driver is None:
        raise HTTPException(
            status_code=503,
            detail="No hay conexion SSH. Usa POST /admin/ssh/connect primero.",
        )
    return _ssh_driver


# ── Modelos ───────────────────────────────────────────────────────────────


class DeployStatusResponse(BaseModel):
    """Estado de un paso del despliegue.

    Atributos:
        step: Nombre del paso ejecutado.
        success: True si se completo correctamente.
        message: Descripcion del resultado.
        output: Salida de consola relevante.
        duration_ms: Duracion en milisegundos.
    """

    step: str
    success: bool
    message: str
    output: str = ""
    duration_ms: float = 0.0


class DeployResultResponse(BaseModel):
    """Resultado de una operacion de despliegue.

    Atributos:
        success: True si todos los pasos se completaron correctamente.
        steps: Lista de pasos ejecutados con su resultado individual.
    """

    success: bool
    steps: list[DeployStatusResponse]


class ScanResultResponse(BaseModel):
    """Resultado del escaneo de red.

    Atributos:
        results: Lista de dispositivos detectados.
        count: Numero total de dispositivos encontrados.
    """

    results: list[dict[str, Any]]
    count: int


class HealthCheckResponse(BaseModel):
    """Resultado de la verificacion de salud.

    Atributos:
        healthy: True si el backend remoto responde.
        message: Descripcion del estado.
        status_code: Codigo HTTP devuelto por el backend remoto.
    """

    healthy: bool
    message: str
    status_code: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────


@router.get("/scan", response_model=ScanResultResponse, dependencies=[Depends(require_admin_api_key_always)])
def deploy_scan() -> ScanResultResponse:
    """Escanea la red local en busca de dispositivos Raspberry Pi.

    Busca hosts con puerto SSH (22) abierto en las subredes locales
    y los reporta como posibles Raspberry Pi.

    No requiere conexion SSH previa (usa sondeo TCP directo).
    Requiere autenticacion: header X-API-Key.
    """
    from backend.app.services.deploy_service import NetworkScanner

    logger.info("Escaneando red local...")
    scan_results: list[ScanResult] = NetworkScanner.scan(timeout=1.0)
    results = [
        {
            "ip": r.ip,
            "hostname": r.hostname or "desconocido",
            "ssh_available": r.ssh_available,
        }
        for r in scan_results
    ]
    return ScanResultResponse(results=results, count=len(results))


@router.post(
    "/setup",
    response_model=DeployResultResponse,
    dependencies=[Depends(require_admin_api_key_always)],
)
def deploy_setup(driver: SSHDriver = Depends(get_ssh_driver)) -> DeployResultResponse:  # noqa: B008
    """Configura el entorno Python en la Raspberry Pi. Requiere autenticacion.

    Crea la estructura de directorios, instala paquetes del sistema,
    crea el entorno virtual (.venv) e instala las dependencias pip.
    """
    logger.info("Iniciando configuracion del entorno...")
    deploy = DeployService(driver)
    steps = deploy.setup_environment()

    return DeployResultResponse(
        success=all(s.success for s in steps),
        steps=[
            DeployStatusResponse(
                step=s.step,
                success=s.success,
                message=s.message,
                output=s.output[:500],
                duration_ms=s.duration_ms,
            )
            for s in steps
        ],
    )


@router.post(
    "/app",
    response_model=DeployResultResponse,
    dependencies=[Depends(require_admin_api_key_always)],
)
def deploy_app(driver: SSHDriver = Depends(get_ssh_driver)) -> DeployResultResponse:  # noqa: B008
    """Despliega los archivos de la aplicacion en la Raspberry Pi. Requiere autenticacion.

    Copia todos los archivos .py, .yaml y .txt del proyecto local
    al directorio remoto usando SFTP.
    """
    logger.info("Iniciando despliegue de archivos...")
    deploy = DeployService(driver)
    steps = deploy.deploy_app()

    return DeployResultResponse(
        success=all(s.success for s in steps),
        steps=[
            DeployStatusResponse(
                step=s.step,
                success=s.success,
                message=s.message,
                output=s.output[:500],
                duration_ms=s.duration_ms,
            )
            for s in steps
        ],
    )


@router.get(
    "/diagnostics",
    response_model=DeployStatusResponse,
    dependencies=[Depends(require_admin_api_key_always)],
)
def deploy_diagnostics(driver: SSHDriver = Depends(get_ssh_driver)) -> DeployStatusResponse:  # noqa: B008
    """Ejecuta el script de diagnostico en la Raspberry Pi. Requiere autenticacion.

    Recopila informacion del sistema (SO, GPIO, pantalla, red, etc.)
    y la devuelve en la respuesta.
    """
    logger.info("Ejecutando diagnostico remoto...")
    deploy = DeployService(driver)
    result = deploy.run_diagnostics()

    return DeployStatusResponse(
        step=result.step,
        success=result.success,
        message=result.message,
        output=result.output[:2000],
        duration_ms=result.duration_ms,
    )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    dependencies=[Depends(require_admin_api_key_always)],
)
def deploy_health(driver: SSHDriver = Depends(get_ssh_driver)) -> HealthCheckResponse:  # noqa: B008
    """Verifica que el backend FastAPI responde en la Raspberry Pi. Requiere autenticacion.

    Realiza una peticion HTTP desde la propia Pi a localhost:8000/health
    para confirmar que el servidor esta operativo.
    """
    logger.info("Verificando salud del backend remoto...")
    deploy = DeployService(driver)
    result = deploy.health_check()

    return HealthCheckResponse(
        healthy=result.success,
        message=result.message,
        status_code=result.output.strip(),
    )


@router.post(
    "/start",
    response_model=DeployStatusResponse,
    dependencies=[Depends(require_admin_api_key_always)],
)
def deploy_start(driver: SSHDriver = Depends(get_ssh_driver)) -> DeployStatusResponse:  # noqa: B008
    """Inicia el backend FastAPI en la Raspberry Pi. Requiere autenticacion.

    Lanza uvicorn en segundo plano en el puerto 8000.
    Si ya hay una instancia corriendo, la detiene primero.
    """
    logger.info("Iniciando backend remoto...")
    deploy = DeployService(driver)
    result = deploy.start_backend()

    return DeployStatusResponse(
        step=result.step,
        success=result.success,
        message=result.message,
        output=result.output,
        duration_ms=result.duration_ms,
    )


@router.post(
    "/stop",
    response_model=DeployStatusResponse,
    dependencies=[Depends(require_admin_api_key_always)],
)
def deploy_stop(driver: SSHDriver = Depends(get_ssh_driver)) -> DeployStatusResponse:  # noqa: B008
    """Detiene el backend FastAPI en la Raspberry Pi. Requiere autenticacion.

    Envia SIGTERM al proceso uvicorn remoto.
    """
    logger.info("Deteniendo backend remoto...")
    deploy = DeployService(driver)
    result = deploy.stop_backend()

    return DeployStatusResponse(
        step=result.step,
        success=result.success,
        message=result.message,
        output=result.output,
        duration_ms=result.duration_ms,
    )
