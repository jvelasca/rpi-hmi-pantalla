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
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.app.models.hmi import ButtonState, DisplayCommand, DisplaySettings, LedState, SystemStatus
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
async def get_display_info() -> dict[str, Any]:
    """Informacion del display fisico conectado.

    Returns:
        Dict con connected, resolution y driver, o error 404 si no conectado.
    """
    display = state_manager.display
    if display is None:
        raise HTTPException(status_code=404, detail="Display no detectado")
    return display.model_dump()


# ── Display Settings (fuente / tamano de texto) ────────────────


@router.get("/settings/display", response_model=DisplaySettings)
async def get_display_settings() -> DisplaySettings:
    """Ajustes visuales actuales del display fisico (fuente y tamano)."""
    return state_manager.get_display_settings()


@router.post("/settings/display", response_model=DisplaySettings)
async def set_display_settings(request: DisplaySettings) -> DisplaySettings:
    """Actualiza los ajustes visuales del display fisico.

    Se persiste en SQLite y se propaga al display fisico por WebSocket.
    """
    return state_manager.set_display_settings(
        request.font_family, request.text_size
    )


# ── Comando de vista al display ────────────────────────────────


@router.post("/display/command")
async def display_command(request: DisplayCommand) -> dict[str, Any]:
    """Envia un comando de cambio de vista al display fisico.

    Permite que el panel web controle la vista mostrada en la pantalla
    de la Pi (ej. prueba de pantalla, calibracion tactil...).
    """
    state_manager.send_display_command(request.action)
    return {"success": True, "action": request.action}
