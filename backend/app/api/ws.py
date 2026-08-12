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

Mensajes Servidor -> Cliente:
    {"version": "1.0", "type": "status_update", "data": {...}, "sequence": 0, "timestamp": "..."}
    {"version": "1.0", "type": "led_changed", "data": {...}, "sequence": 1, "timestamp": "..."}
    {"version": "1.0", "type": "button_pressed", "data": {...}, "sequence": 2, "timestamp": "..."}
    {"version": "1.0", "type": "button_released", "data": {...}, "sequence": 3, "timestamp": "..."}
    {"version": "1.0", "type": "error", "data": {"code": "...", "message": "..."}, "timestamp": "..."}
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.models.events import ClientMessage, ServerMessage
from backend.app.services.state_manager import state_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Version de protocolo soportada
SUPPORTED_VERSION = "1.0"


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Endpoint WebSocket principal.

    Maneja la conexion, suscripcion, recepcion de comandos
    y desconexion limpia.

    Valida la version del protocolo: rechaza mensajes con
    version != "1.0" enviando PROTOCOL_VERSION_MISMATCH.

    Args:
        websocket: Conexion WebSocket entrante.
    """
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
                    ).model_dump()
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
                            data=status.model_dump(),
                        ).model_dump()
                    )

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
                        ).model_dump()
                    )

    except WebSocketDisconnect:
        logger.info("Cliente WS desconectado")
    except Exception as exc:
        logger.exception("Error en WebSocket")
        try:
            await websocket.send_json(
                ServerMessage(
                    type="error",
                    data={
                        "code": "INTERNAL_ERROR",
                        "message": str(exc),
                    },
                ).model_dump()
            )
        except Exception:
            pass
    finally:
        state_manager.unsubscribe(websocket)
