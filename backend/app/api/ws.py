"""Handler WebSocket para comunicacion en tiempo real.

Protocolo basado en JSON con discriminacion por campo `type`.

Conexion: ws://<host>:8000/ws

Mensajes Cliente -> Servidor:
    {"type": "toggle_led"}
    {"type": "press_button"}
    {"type": "release_button"}
    {"type": "get_status"}
    {"type": "subscribe", "topics": ["led", "button", "display"]}

Mensajes Servidor -> Cliente:
    {"type": "status_update", "data": {...}, "timestamp": "..."}
    {"type": "led_changed", "data": {...}, "timestamp": "..."}
    {"type": "button_pressed", "data": {...}, "timestamp": "..."}
    {"type": "button_released", "data": {...}, "timestamp": "..."}
    {"type": "error", "data": {"code": "...", "message": "..."}, "timestamp": "..."}
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.models.events import ClientMessage, ServerMessage
from backend.app.services.state_manager import state_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Endpoint WebSocket principal.

    Maneja la conexion, suscripcion, recepcion de comandos
    y desconexion limpia.

    Args:
        websocket: Conexion WebSocket entrante.
    """
    await websocket.accept()
    logger.info("Cliente WS conectado")

    try:
        while True:
            raw = await websocket.receive_json()
            msg = ClientMessage.model_validate(raw)
            logger.debug("WS recibido: type=%s", msg.type)

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
