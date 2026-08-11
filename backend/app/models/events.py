"""Esquemas de mensajes para el protocolo WebSocket.

Define los tipos de mensajes que viajan entre cliente y servidor,
con validacion Pydantic estricta y discriminacion por campo `type`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────


class SubscriptionTopic(StrEnum):
    """Topicos a los que un cliente puede suscribirse."""

    LED = "led"
    BUTTON = "button"
    DISPLAY = "display"
    SYSTEM = "system"


class EventType(StrEnum):
    """Tipos de eventos del protocolo WebSocket."""

    # Cliente -> Servidor
    TOGGLE_LED = "toggle_led"
    PRESS_BUTTON = "press_button"
    RELEASE_BUTTON = "release_button"
    GET_STATUS = "get_status"
    SUBSCRIBE = "subscribe"
    # Servidor -> Cliente
    STATUS_UPDATE = "status_update"
    LED_CHANGED = "led_changed"
    BUTTON_PRESSED = "button_pressed"
    BUTTON_RELEASED = "button_released"
    DISPLAY_CHANGED = "display_changed"
    ERROR = "error"


# ── Mensajes Cliente -> Servidor ───────────────────────────────


class ClientMessage(BaseModel):
    """Mensaje recibido de un cliente WebSocket.

    El campo `type` discrimina la accion solicitada.
    Campos adicionales dependen del tipo.

    Examples:
        >>> ClientMessage(type="toggle_led")
        >>> ClientMessage(type="subscribe", topics=["led", "button"])
    """

    version: Annotated[
        str,
        Field(default="1.0", description="Version del protocolo WebSocket"),
    ]
    type: Annotated[
        Literal[
            "toggle_led",
            "press_button",
            "release_button",
            "get_status",
            "subscribe",
        ],
        Field(description="Tipo de accion solicitada"),
    ]
    topics: Annotated[
        list[SubscriptionTopic] | None,
        Field(default=None, description="Topicos a suscribir (solo con 'subscribe')"),
    ]


# ── Mensajes Servidor -> Cliente ───────────────────────────────


class ErrorDetail(BaseModel):
    """Detalle de un error transmitido al cliente.

    Attributes:
        code: Codigo de error legible por maquina (ej. 'DEVICE_NOT_FOUND').
        message: Descripcion legible en espanol.
    """

    code: Annotated[str, Field(description="Codigo de error maquina")]
    message: Annotated[str, Field(description="Mensaje legible")]


class ServerMessage(BaseModel):
    """Mensaje enviado por el servidor a los clientes WebSocket.

    El campo `type` discrimina el tipo de evento.
    `data` contiene el payload especifico del evento.

    Examples:
        >>> ServerMessage(type="led_changed", data={"state": True})
        >>> ServerMessage(type="error", data={"code": "GPIO_BUSY", "message": "GPIO 17 ocupado"})
    """

    version: Annotated[
        str,
        Field(default="1.0", description="Version del protocolo WebSocket"),
    ]
    type: Annotated[
        Literal[
            "status_update",
            "led_changed",
            "button_pressed",
            "button_released",
            "display_changed",
            "error",
        ],
        Field(description="Tipo de evento"),
    ]
    data: Annotated[dict, Field(description="Payload del evento")]
    timestamp: Annotated[
        datetime,
        Field(
            default_factory=lambda: datetime.now(timezone.utc),
            description="Timestamp UTC del evento",
        ),
    ]
