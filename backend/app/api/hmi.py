"""Endpoints REST de la API HMI.

Proporciona operaciones CRUD sobre LED, boton y estado del sistema.
Todos los endpoints usan modelos Pydantic para validacion estricta.

Endpoints:
    GET  /api/status        -> Estado completo del sistema
    GET  /api/led           -> Estado del LED
    POST /api/led/toggle    -> Alternar LED
    POST /api/led/on        -> Encender LED
    POST /api/led/off       -> Apagar LED
    GET  /api/button        -> Estado del boton
    POST /api/button/press  -> Presionar boton
    POST /api/button/release -> Soltar boton
    GET  /api/display/info  -> Info del display fisico
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.app.models.hmi import ButtonState, LedState, SystemStatus
from backend.app.services.state_manager import state_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["HMI"])


# ── Status ────────────────────────────────────────────────────


@router.get("/status", response_model=SystemStatus)
async def get_status() -> SystemStatus:
    """Estado completo del sistema: LED, boton, display, uptime, CPU, clientes WS.

    Returns:
        SystemStatus con todos los subsistemas agregados.
    """
    return state_manager.get_status()


# ── LED ────────────────────────────────────────────────────────


@router.get("/led", response_model=LedState)
async def get_led() -> LedState:
    """Estado actual del LED.

    Returns:
        LedState con estado, etiqueta y pin GPIO.
    """
    return state_manager.led


@router.post("/led/toggle", response_model=LedState)
async def toggle_led() -> LedState:
    """Alterna el estado del LED (ON <-> OFF).

    Returns:
        Nuevo LedState tras el toggle.
    """
    return state_manager.toggle_led()


@router.post("/led/on", response_model=LedState)
async def led_on() -> LedState:
    """Enciende el LED.

    Returns:
        LedState confirmando encendido.
    """
    return state_manager.set_led(True)


@router.post("/led/off", response_model=LedState)
async def led_off() -> LedState:
    """Apaga el LED.

    Returns:
        LedState confirmando apagado.
    """
    return state_manager.set_led(False)


# ── Button ─────────────────────────────────────────────────────


@router.get("/button", response_model=ButtonState)
async def get_button() -> ButtonState:
    """Estado actual del boton.

    Returns:
        ButtonState con estado de presion y contador acumulado.
    """
    return state_manager.button


@router.post("/button/press", response_model=ButtonState)
async def press_button() -> ButtonState:
    """Registra una pulsacion del boton (incrementa contador).

    Returns:
        ButtonState actualizado.
    """
    return state_manager.press_button()


@router.post("/button/release", response_model=ButtonState)
async def release_button() -> ButtonState:
    """Libera el boton.

    Returns:
        ButtonState actualizado.
    """
    return state_manager.release_button()


# ── Display Info ───────────────────────────────────────────────


@router.get("/display/info")
async def get_display_info() -> dict:
    """Informacion del display fisico conectado.

    Returns:
        Dict con connected, resolution y driver, o error 404 si no conectado.
    """
    display = state_manager.display
    if display is None:
        raise HTTPException(status_code=404, detail="Display no detectado")
    return display.model_dump()
