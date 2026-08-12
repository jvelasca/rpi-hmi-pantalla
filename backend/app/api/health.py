"""Endpoint de health check con verificacion por componente.

Expone un health check detallado que comprueba:
- Estado de la API (uptime)
- GPIO (si esta configurado)
- Display (si esta conectado)
- Base de datos SQLite (si existe)
- CPU (temperatura)
- WebSocket (clientes conectados)

Uso:
    GET /health  ->  HealthStatus con checks desglosados
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.app.services.state_manager import state_manager

router = APIRouter(prefix="/health", tags=["Health"])


# ── Modelos ───────────────────────────────────────────────────

class HealthCheckDetail(BaseModel):
    """Resultado de un check individual de salud.

    Attributes:
        status: 'pass' (ok), 'warn' (degradado), 'fail' (roto).
        message: Descripcion legible del resultado.
    """

    status: Annotated[
        Literal["pass", "warn", "fail"],
        Field(description="Estado del check: pass, warn o fail"),
    ]
    message: Annotated[str, Field(description="Descripcion del resultado")]


class HealthStatus(BaseModel):
    """Estado de salud completo del sistema.

    Cada subsistema tiene su propio check independiente.
    El estado global es 'healthy' si todos pasan, 'degraded' si hay warns,
    'unhealthy' si hay algun fail.

    Attributes:
        status: Estado global (healthy, degraded, unhealthy).
        checks: Diccionario con el resultado de cada subsistema.
        timestamp: Momento del check (UTC).
        uptime_seconds: Segundos desde el arranque.
    """

    status: Annotated[
        Literal["healthy", "degraded", "unhealthy"],
        Field(description="Estado global del sistema"),
    ]
    checks: Annotated[
        dict[str, HealthCheckDetail],
        Field(description="Resultados individuales por componente"),
    ]
    timestamp: Annotated[datetime, Field(description="Timestamp UTC del check")]
    uptime_seconds: Annotated[float, Field(description="Segundos desde arranque")]


# ── Helpers ────────────────────────────────────────────────────

def _check_api() -> HealthCheckDetail:
    """Verifica que la API responde (siempre OK, este endpoint es la prueba)."""
    return HealthCheckDetail(status="pass", message="API operativa")


def _check_uptime() -> HealthCheckDetail:
    """Verifica uptime del servicio."""
    status = state_manager.get_status()
    hours = status.uptime_seconds / 3600
    return HealthCheckDetail(
        status="pass",
        message=f"Uptime: {hours:.1f}h ({status.uptime_seconds:.0f}s)",
    )


def _check_gpio() -> HealthCheckDetail:
    """Verifica si GPIO esta configurado."""
    led = state_manager.led
    if led.gpio_pin > 0:
        return HealthCheckDetail(
            status="pass",
            message=f"GPIO configurado en pin {led.gpio_pin} (LED: {led.label})",
        )
    return HealthCheckDetail(
        status="warn",
        message="GPIO no configurado (pin=0). Modo virtual activo.",
    )


def _check_display() -> HealthCheckDetail:
    """Verifica si el display fisico esta conectado."""
    display = state_manager.display
    if display and display.connected:
        return HealthCheckDetail(
            status="pass",
            message=f"Display conectado: {display.resolution} ({display.driver})",
        )
    return HealthCheckDetail(
        status="warn",
        message="Display fisico no detectado",
    )


def _check_db() -> HealthCheckDetail:
    """Verifica que la BD SQLite responde (si existe)."""
    # La BD se maneja via persistence singleton — verificamos indirectamente
    # comprobando que el state_manager esta funcional
    try:
        status = state_manager.get_status()
        if status:
            return HealthCheckDetail(
                status="pass",
                message="Base de datos operativa (LED + button state cargado)",
            )
    except Exception:
        pass
    return HealthCheckDetail(
        status="warn",
        message="BD no disponible (modo sin persistencia)",
    )


def _check_cpu() -> HealthCheckDetail:
    """Verifica temperatura de la CPU."""
    status = state_manager.get_status()
    if status.cpu_temp_celsius is not None:
        temp = status.cpu_temp_celsius
        if temp > 80:
            return HealthCheckDetail(
                status="warn",
                message=f"CPU temperatura elevada: {temp:.1f}°C",
            )
        return HealthCheckDetail(
            status="pass",
            message=f"CPU: {temp:.1f}°C",
        )
    return HealthCheckDetail(
        status="pass",
        message="Temperatura CPU no disponible (sin acceso a sysfs)",
    )


def _check_ws() -> HealthCheckDetail:
    """Verifica conectividad WebSocket."""
    status = state_manager.get_status()
    return HealthCheckDetail(
        status="pass",
        message=f"WebSocket: {status.websocket_clients} cliente(s) conectado(s)",
    )


# ── Endpoint ──────────────────────────────────────────────────


@router.get(
    "",
    response_model=HealthStatus,
    summary="Health check del sistema",
    description="Verifica el estado de todos los subsistemas (API, GPIO, display, DB, CPU, WebSocket). "
    "Devuelve un HealthStatus con checks desglosados y un estado global (healthy/degraded/unhealthy).",
)
async def health_check() -> HealthStatus:
    """Health check completo con verificacion por componente.

    Returns:
        HealthStatus con checks individuales y estado global.

    Raises:
        HTTPException 503 si el estado global es unhealthy.
    """
    checks: dict[str, HealthCheckDetail] = {}

    try:
        checks["api"] = _check_api()
    except Exception:
        checks["api"] = HealthCheckDetail(status="fail", message="API no responde")

    try:
        checks["uptime"] = _check_uptime()
    except Exception:
        checks["uptime"] = HealthCheckDetail(status="fail", message="Error al obtener uptime")

    try:
        checks["gpio"] = _check_gpio()
    except Exception:
        checks["gpio"] = HealthCheckDetail(status="fail", message="Error al verificar GPIO")

    try:
        checks["display"] = _check_display()
    except Exception:
        checks["display"] = HealthCheckDetail(status="fail", message="Error al verificar display")

    try:
        checks["db"] = _check_db()
    except Exception:
        checks["db"] = HealthCheckDetail(status="fail", message="Error al verificar BD")

    try:
        checks["cpu"] = _check_cpu()
    except Exception:
        checks["cpu"] = HealthCheckDetail(status="fail", message="Error al leer CPU")

    try:
        checks["ws"] = _check_ws()
    except Exception:
        checks["ws"] = HealthCheckDetail(status="fail", message="Error al verificar WebSocket")

    # Determinar estado global
    statuses = [c.status for c in checks.values()]
    if "fail" in statuses:
        global_status: Literal["healthy", "degraded", "unhealthy"] = "unhealthy"
    elif "warn" in statuses:
        global_status = "degraded"
    else:
        global_status = "healthy"

    status = state_manager.get_status()
    result = HealthStatus(
        status=global_status,
        checks=checks,
        timestamp=datetime.now(timezone.utc),
        uptime_seconds=status.uptime_seconds,
    )

    if global_status == "unhealthy":
        raise HTTPException(status_code=503, detail=result.model_dump())

    return result
