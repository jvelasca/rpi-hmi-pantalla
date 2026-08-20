"""Handler WebSocket para comunicacion en tiempo real.

Protocolo basado en JSON con discriminacion por campo `type`.

Conexion: ws://<host>:8000/ws

Version de protocolo soportada: 1.0
Mensajes con version != "1.0" reciben PROTOCOL_VERSION_MISMATCH.

Mensajes Cliente -> Servidor:
    {"version": "1.0", "type": "toggle_led"}
    {"version": "1.0", "type": "press_button"}
    {"version": "1.0", "type": "release_button"}
    {"version": "1.0", "type": "get_status"}
    {"version": "1.0", "type": "subscribe", "topics": ["led", "button", "display"]}
    {"version": "1.0", "type": "display_command", "action": "screen_test"}

Mensajes Servidor -> Cliente:
    {"version": "1.0", "type": "status_update", "data": {...}, "sequence": 0, "timestamp": "..."}
    {"version": "1.0", "type": "led_changed", "data": {...}, "sequence": 1, "timestamp": "..."}
    {"version": "1.0", "type": "button_pressed", "data": {...}, "sequence": 2, "timestamp": "..."}
    {"version": "1.0", "type": "button_released", "data": {...}, "sequence": 3, "timestamp": "..."}
    {"version": "1.0", "type": "error", "data": {"code": "...", "message": "..."}, "timestamp": "..."}
"""

from __future__ import annotations

import contextlib
import logging
import secrets as _secrets
from collections.abc import Mapping

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.config import settings
from backend.app.models.events import ClientMessage, ServerMessage
from backend.app.services.state_manager import state_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Version de protocolo soportada
SUPPORTED_VERSION = "1.0"

# Hosts de loopback considerados de confianza en modo ``protected``.
# El display fisico (Pygame) se conecta a ws://localhost:8000/ws desde la
# propia Pi, por lo que estas conexiones no requieren X-API-Key.
_LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")


def _is_loopback(host: str | None) -> bool:
    """Devuelve True si el host del cliente es loopback (display local)."""
    return (host or "").lower() in _LOOPBACK_HOSTS


def _extract_api_key(headers: object) -> str | None:
    """Lee ``X-API-Key`` de los headers del handshake (case-insensitive)."""
    if not isinstance(headers, Mapping):
        return None
    for key, value in headers.items():
        if str(key).lower() == "x-api-key":
            return str(value)
    return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Endpoint WebSocket principal.

    Maneja la conexion, suscripcion, recepcion de comandos
    y desconexion limpia.

    Autenticacion:
    - ``SECURITY_MODE == "local"``: acepta a todos.
    - ``SECURITY_MODE == "protected"``: acepta conexiones desde loopback
      (display local de confianza); el resto debe enviar ``X-API-Key``
      igual a ``settings.admin_api_key``.

    Valida la version del protocolo: rechaza mensajes con
    version != "1.0" enviando PROTOCOL_VERSION_MISMATCH.

    Args:
        websocket: Conexion WebSocket entrante.
    """
    if settings.security_mode == "protected":
        client_host = websocket.client.host if websocket.client else None
        if not _is_loopback(client_host):
            api_key = _extract_api_key(websocket.headers)
            if not api_key or not _secrets.compare_digest(api_key, settings.admin_api_key or ""):
                logger.warning(
                    "WS rechazado por auth fallida (host=%s)",
                    client_host,
                )
                await websocket.close(code=4401)
                return

    await websocket.accept()
    logger.info("Cliente WS conectado")

    try:
        while True:
            raw = await websocket.receive_json()
            msg = ClientMessage.model_validate(raw)

            # Validar version del protocolo
            if msg.version != SUPPORTED_VERSION:
                await websocket.send_json(
                    ServerMessage(
                        type="error",
                        data={
                            "code": "PROTOCOL_VERSION_MISMATCH",
                            "message": (
                                f"Version de protocolo no soportada: {msg.version}. "
                                f"Esperada: {SUPPORTED_VERSION}"
                            ),
                        },
                    ).model_dump(mode="json")
                )
                logger.warning(
                    "Version WS no soportada: %s (esperada %s)",
                    msg.version, SUPPORTED_VERSION,
                )
                continue

            logger.debug("WS recibido: type=%s version=%s", msg.type, msg.version)

            match msg.type:
                case "toggle_led":
                    state_manager.toggle_led()

                case "press_button":
                    state_manager.press_button()

                case "release_button":
                    state_manager.release_button()

                case "get_status":
                    status = state_manager.get_status()
                    await websocket.send_json(
                        ServerMessage(
                            type="status_update",
                            data=status.model_dump(mode="json"),
                        ).model_dump(mode="json")
                    )

                case "display_command":
                    action = msg.action or ""
                    state_manager.send_display_command(action)

                case "subscribe":
                    await state_manager.subscribe(
                        websocket,
                        topics=msg.topics,
                    )

                case _:
                    await websocket.send_json(
                        ServerMessage(
                            type="error",
                            data={
                                "code": "UNKNOWN_TYPE",
                                "message": f"Tipo de mensaje desconocido: {msg.type}",
                            },
                        ).model_dump(mode="json")
                    )

    except WebSocketDisconnect:
        logger.info("Cliente WS desconectado")
    except Exception as exc:
        logger.exception("Error en WebSocket")
        with contextlib.suppress(Exception):
            await websocket.send_json(
                ServerMessage(
                    type="error",
                    data={
                        "code": "INTERNAL_ERROR",
                        "message": str(exc),
                    },
                ).model_dump(mode="json")
            )
    finally:
        state_manager.unsubscribe(websocket)
