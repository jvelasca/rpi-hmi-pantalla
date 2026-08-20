"""Punto de entrada de la aplicacion FastAPI.

Crea la app, registra routers, configura CORS, monta archivos estaticos
y gestiona el ciclo de vida (lifespan) de los servicios.

Ejecucion:
    uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
    python -m backend.app.main
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api import (
    admin_deploy_router,
    admin_ssh_router,
    health_router,
    hmi_router,
    network_router,
    ws_router,
)
from backend.app.config import settings
from backend.app.services.gpio_service import gpio_service
from backend.app.services.state_manager import state_manager
from backend.app.services.systemd_notify import (
    notify_ready,
    notify_stopping,
    notify_watchdog,
    watchdog_interval_usec,
)

logger = logging.getLogger("rpi_hmi.backend")

# ── Configurar logging ────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ── Lifespan ──────────────────────────────────────────────────


async def _watchdog_loop(interval_usec: int) -> None:
    """Envia WATCHDOG=1 a systemd periodicamente (mitad de WatchdogSec)."""
    interval_sec = interval_usec / 1_000_000
    try:
        while True:
            await asyncio.sleep(interval_sec)
            try:
                notify_watchdog()
            except Exception:
                logger.exception("Error enviando WATCHDOG=1 a systemd")
    except asyncio.CancelledError:
        logger.info("Watchdog systemd detenido")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestiona el ciclo de vida de la aplicacion.

    Startup:
    - Lee configuracion de pines desde devices.yaml (fuente unica de verdad)
    - Registra callback de actualizacion hardware
    - Detecta display fisico

    Shutdown:
    - Limpia GPIO
    """
    logger.info("=" * 50)
    logger.info("  RPi HMI Backend iniciando...")
    logger.info("=" * 50)

    # Configurar GPIO — leer pin desde devices.yaml (fuente unica de verdad)
    try:
        from backend.app.models.device import DeviceType
        from backend.app.services.gpio_service import load_devices

        # Usar ruta absoluta relativa a este archivo (main.py)
        devices_path = str(
            Path(__file__).resolve().parents[1] / "config" / "devices.yaml"
        )
        devices = load_devices(devices_path)
        led_pin = 0
        for dev_id, dev in devices.items():
            if dev.type == DeviceType.DIGITAL_OUTPUT and dev.pin:
                led_pin = dev.pin.bcm
                logger.info(
                    "Dispositivo GPIO detectado: %s en pin %d (%s)",
                    dev_id,
                    led_pin,
                    dev.name,
                )
                break

        if led_pin > 0:
            gpio_service.setup_output(led_pin)
            logger.info("GPIO %d configurado como salida (LED)", led_pin)
        else:
            logger.warning(
                "No se encontro pin GPIO output en devices.yaml. "
                "El LED funcionara en modo virtual (sin GPIO fisico). "
                "Verifica backend/config/devices.yaml"
            )

        # Conectar StateManager con GPIO via callback
        def _update_led(device: str, led_state: object) -> None:
            from backend.app.models.hmi import LedState

            if isinstance(led_state, LedState) and led_state.gpio_pin > 0:
                gpio_service.set_state(led_state.gpio_pin, led_state.state)

        state_manager.set_updater(_update_led)
        logger.info("Callback GPIO registrado en StateManager")
    except Exception as exc:
        logger.warning("No se pudo inicializar GPIO: %s", exc)

    # Detectar display
    try:
        if Path("/dev/dri/card0").exists():
            state_manager.set_display(connected=True, resolution="480x320", driver="piscreen")
            logger.info("Display detectado: piscreen DRM")
        elif Path("/dev/fb1").exists():
            state_manager.set_display(connected=True, resolution="480x320", driver="ili9486")
            logger.info("Display detectado: ili9486 framebuffer")
        else:
            logger.warning("Display fisico no detectado")
    except Exception:
        logger.warning("Display no disponible")

    # Auto-conexion SSH — solo cuando la admin API esta habilitada
    if settings.enable_admin_api:
        try:
            from backend.app.api.ssh import auto_connect_ssh

            await auto_connect_ssh()
        except Exception as exc:
            logger.debug("Auto-conexion SSH ignorada: %s", exc)

    # Inicializar persistencia SQLite
    try:
        from backend.app.services.persistence import get_persistence

        db = await get_persistence(settings.db_path)
        state_manager.set_persistence(db)
        await state_manager.restore_from_db()
        logger.info("Persistencia SQLite inicializada en %s", settings.db_path)
    except Exception as exc:
        logger.warning("Persistencia SQLite no disponible: %s", exc)

    # ── systemd sd_notify ─────────────────────────────────────
    # No-op si no corre bajo systemd (Windows/CI/dev): notify_ready()
    # retorna False sin error y watchdog_interval_usec() retorna None.
    watchdog_task: asyncio.Task[None] | None = None
    try:
        notify_ready()
        interval_usec = watchdog_interval_usec()
        if interval_usec is not None:
            watchdog_task = asyncio.create_task(_watchdog_loop(interval_usec))
            logger.info(
                "Watchdog systemd activado: WATCHDOG=1 cada %.1f s",
                interval_usec / 1_000_000,
            )
    except Exception as exc:
        logger.warning("sd_notify no disponible: %s", exc)

    yield  # ── App corriendo ──

    # Shutdown
    logger.info("Apagando servicios...")

    # Detener watchdog systemd antes de cerrar servicios
    if watchdog_task is not None:
        watchdog_task.cancel()
        try:
            await watchdog_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning("Error al cancelar watchdog systemd", exc_info=True)

    try:
        notify_stopping()
    except Exception as exc:
        logger.warning("No se pudo notificar STOPPING=1 a systemd: %s", exc)

    # Drain pending persistence tasks before closing DB
    try:
        await state_manager.flush_pending_tasks()
    except Exception as exc:
        logger.warning("Error draining persistence tasks: %s", exc)

    try:
        gpio_service.cleanup()
    except Exception as exc:
        logger.warning("Error en cleanup GPIO: %s", exc)
    # Cerrar persistencia
    try:
        from backend.app.services.persistence import close_persistence
        await close_persistence()
    except Exception as exc:
        logger.warning("Error al cerrar persistencia: %s", exc)
    logger.info("RPi HMI Backend detenido.")


# ── App ───────────────────────────────────────────────────────

# Deshabilitar docs en produccion segun configuracion
_docs_url = "/docs" if settings.enable_docs else None
_redoc_url = "/redoc" if settings.enable_docs else None

app = FastAPI(
    title="RPi HMI Backend",
    description=(
        "Backend para panel de control HMI en Raspberry Pi. "
        "Controla GPIO, display fisico y expone API REST + WebSocket."
    ),
    version="0.3.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

# CORS — origenes controlados desde configuracion
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept", "X-API-Key"],
)

# Routers HMI (sin autenticacion, acceso LAN)
app.include_router(hmi_router)
app.include_router(ws_router)
app.include_router(network_router)

# Health check (publico)
app.include_router(health_router)

# Routers administrativos — solo cuando la admin API esta habilitada
if settings.enable_admin_api:
    app.include_router(admin_ssh_router)
    app.include_router(admin_deploy_router)
    logger.warning("ADMIN_API habilitada. Deshabilita con ENABLE_ADMIN_API=false en .env para produccion.")

# ── Frontend SolidJS compilado ────────────────────────────────
# Montado DESPUES de todos los routers. FastAPI prueba primero
# las rutas registradas (API, WS, health) y solo si no hay match
# sirve archivos estaticos del frontend compilado con Vite.
#
# html=True permite SPA routing: cualquier ruta no encontrada en
# el directorio estatico sirve index.html como fallback.
#
# Si el frontend no esta compilado (modo desarrollo/sin npm build),
# se registra un endpoint JSON informativo en su lugar.

# parents[2]: main.py -> app -> backend -> rpi_hmi (raiz del proyecto)
dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if dist_dir.exists() and (dist_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
else:
    @app.get("/")
    async def root() -> JSONResponse:
        return JSONResponse(content={
            "message": "RPi HMI Backend",
            "version": "0.3.0",
            "docs": "/docs" if settings.enable_docs else "deshabilitado",
            "api": "/api/status",
            "websocket": "/ws",
            "frontend": "No compilado. Ejecuta: cd frontend && npm run build",
        })


# ── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        log_level=settings.log_level,
        reload=False,
    )
