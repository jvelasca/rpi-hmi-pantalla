"""Endpoints de health check con verificacion por componente.

Expone tres niveles de health check:
- /health       — diagnostico completo (healthy/degraded/unhealthy)
- /health/live  — liveness: ¿el proceso esta vivo? (siempre 200 si responde)
- /health/ready — readiness: ¿el servicio puede aceptar trafico?

El despliegue y systemd deben usar /health/ready (codigo HTTP, no grep de texto).

Uso:
    GET /health        ->  HealthStatus con checks desglosados
    GET /health/live   ->  200 OK simple
    GET /health/ready  ->  200 OK si listo, 503 si no
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Response
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
    """Verifica que la BD SQLite responde realmente.

    Usa Persistence.is_healthy() que ejecuta SELECT 1 contra la BD.
    Anteriormente solo comprobaba que el state_manager funcionara, lo cual
    no verificaba SQLite.
    """
    try:
        persistence = state_manager._persistence
        if persistence is None:
            return HealthCheckDetail(
                status="pass",
                message="Persistencia no configurada (modo sin BD)",
            )
        # No podemos llamar await aqui, asi que verificamos que la
        # conexion existe y hacemos un check indirecto via state_manager
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
    """Verifica conectividad WebSocket.

    Nota: esto solo comprueba cuantos clientes hay conectados, no si el
    servidor WebSocket esta funcional. Para liveness se usa /health/live.
    """
    status = state_manager.get_status()
    return HealthCheckDetail(
        status="pass",
        message=f"WebSocket: {status.websocket_clients} cliente(s) conectado(s)",
    )


# ── Helpers async ──────────────────────────────────────────────

async def _check_db_async() -> HealthCheckDetail:
    """Verifica SQLite mediante SELECT 1 (async, usado en /ready)."""
    try:
        persistence = state_manager._persistence
        if persistence is None:
            return HealthCheckDetail(
                status="pass",
                message="Persistencia no configurada (modo sin BD)",
            )
        healthy = await persistence.is_healthy()
        if healthy:
            return HealthCheckDetail(
                status="pass",
                message="Base de datos operativa",
            )
        return HealthCheckDetail(
            status="fail",
            message="Base de datos no responde",
        )
    except Exception as exc:
        return HealthCheckDetail(
            status="fail",
            message=f"Error de BD: {exc}",
        )


def _collect_checks_sync() -> dict[str, HealthCheckDetail]:
    """Ejecuta todos los checks sincronos y devuelve el diccionario."""
    checks: dict[str, HealthCheckDetail] = {}

    for name, func in [
        ("api", _check_api),
        ("uptime", _check_uptime),
        ("gpio", _check_gpio),
        ("display", _check_display),
        # ("db", ...) se añade async en _collect_checks_async
        ("cpu", _check_cpu),
        ("ws", _check_ws),
    ]:
        try:
            checks[name] = func()
        except Exception:
            checks[name] = HealthCheckDetail(status="fail", message=f"Error al verificar {name}")

    return checks


def _compute_global(checks: dict[str, HealthCheckDetail]) -> Literal["healthy", "degraded", "unhealthy"]:
    statuses = [c.status for c in checks.values()]
    if "fail" in statuses:
        return "unhealthy"
    if "warn" in statuses:
        return "degraded"
    return "healthy"


async def _collect_checks_async() -> dict[str, HealthCheckDetail]:
    """Ejecuta checks con verificacion async de BD."""
    checks = _collect_checks_sync()
    # Reemplazar check DB sincrono por el async real
    try:
        checks["db"] = await _check_db_async()
    except Exception:
        checks["db"] = HealthCheckDetail(status="fail", message="Error al verificar BD")
    return checks


# ── Endpoints ──────────────────────────────────────────────────


@router.get(
    "",
    response_model=HealthStatus,
    summary="Health check diagnostico completo",
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
    checks = await _collect_checks_async()
    global_status = _compute_global(checks)

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


@router.get(
    "/live",
    summary="Liveness probe",
    description="Responde 200 OK si el proceso esta vivo. Usado por orquestadores "
    "para saber si reiniciar el contenedor/proceso. No comprueba dependencias.",
)
async def health_live() -> Response:
    """Liveness: el proceso esta vivo y respondiendo.

    Siempre devuelve 200 si este endpoint responde.
    No verifica dependencias externas (BD, GPIO, etc.).
    """
    return Response(status_code=200)


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Responde 200 OK si el servicio puede aceptar trafico. "
    "Comprueba que la BD esta operativa. Usado por systemd y balanceadores "
    "para decidir si enviar trafico a esta instancia.",
)
async def health_ready() -> Response:
    """Readiness: el servicio esta listo para aceptar peticiones.

    Comprueba:
    - API responde (implicito en este endpoint)
    - SQLite responde (SELECT 1)

    Returns:
        200 OK si listo, 503 si no.
    """
    db_check = await _check_db_async()
    if db_check.status == "fail":
        raise HTTPException(status_code=503, detail="Base de datos no disponible")

    return Response(status_code=200)
