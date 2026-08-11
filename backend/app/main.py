"""Punto de entrada de la aplicacion FastAPI.

Crea la app, registra routers, configura CORS, monta archivos estaticos
y gestiona el ciclo de vida (lifespan) de los servicios.

Ejecucion:
    uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
    python -m backend.app.main
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api import hmi_router, ws_router
from backend.app.config import settings
from backend.app.services.gpio_service import gpio_service
from backend.app.services.state_manager import state_manager

logger = logging.getLogger("rpi_hmi.backend")

# ── Configurar logging ────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ── Lifespan ──────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestiona el ciclo de vida de la aplicacion.

    Startup:
    - Configura GPIO para LED en pin 17
    - Registra callback de actualizacion hardware
    - Detecta display fisico

    Shutdown:
    - Limpia GPIO
    """
    logger.info("=" * 50)
    logger.info("  RPi HMI Backend iniciando...")
    logger.info("=" * 50)

    # Configurar GPIO
    try:
        gpio_service.setup_output(17)
        logger.info("GPIO 17 configurado como salida (LED)")

        # Conectar StateManager con GPIO via callback
        def _update_led(device: str, led_state: object) -> None:
            from backend.app.models.hmi import LedState

            if isinstance(led_state, LedState):
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

    yield  # ── App corriendo ──

    # Shutdown
    logger.info("Apagando servicios...")
    try:
        gpio_service.cleanup()
    except Exception as exc:
        logger.warning("Error en cleanup GPIO: %s", exc)
    logger.info("RPi HMI Backend detenido.")


# ── App ───────────────────────────────────────────────────────

app = FastAPI(
    title="RPi HMI Backend",
    description="Backend para panel de control HMI en Raspberry Pi. Controla GPIO, display fisico y expone API REST + WebSocket.",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(hmi_router)
app.include_router(ws_router)

# ── Endpoints raiz ───────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check para monitoreo.

    Returns:
        {"status": "ok"}
    """
    return {"status": "ok"}


@app.get("/")
async def root() -> FileResponse:
    """Sirve el frontend compilado (index.html).

    Si no existe, devuelve mensaje informativo.

    Returns:
        FileResponse con index.html o JSON con instrucciones.
    """
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return JSONResponse(
        content={
            "message": "RPi HMI Backend",
            "version": "0.2.0",
            "docs": "/docs",
            "api": "/api/status",
            "websocket": "/ws",
            "frontend": "No compilado. Ejecuta: cd frontend && npm run build",
        }
    )


# ── Montar archivos estaticos ─────────────────────────────────

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


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
