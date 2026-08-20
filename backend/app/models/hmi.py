"""Modelos Pydantic para el estado del HMI.

Define las entidades principales del sistema: LED, boton, display y estado global.
Todos los campos usan `Field` con descripciones para generacion automatica de
documentacion OpenAPI.

Tipos TypeScript equivalentes: frontend/src/types/api.ts
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# ── LED ────────────────────────────────────────────────────────


class LedState(BaseModel):
    """Estado actual del LED fisico conectado a GPIO.

    Attributes:
        state: True si el LED esta encendido, False si apagado.
        label: Etiqueta legible en espanol (ENCENDIDO / APAGADO).
        gpio_pin: Numero de pin BCM del GPIO.
    """

    state: Annotated[bool, Field(description="True = encendido, False = apagado")]
    label: str = Field(description="Etiqueta: ENCENDIDO | APAGADO")
    gpio_pin: Annotated[
        int, Field(default=0, ge=0, le=27, description="Pin BCM del GPIO (cargado desde devices.yaml)")
    ]

    @property
    def is_on(self) -> bool:
        """Alías semántico para state."""
        return self.state


# ── Button ─────────────────────────────────────────────────────


class ButtonState(BaseModel):
    """Estado del boton fisico o virtual.

    Attributes:
        pressed: True si el boton esta siendo presionado.
        press_count: Contador acumulativo de pulsaciones desde el arranque.
    """

    pressed: Annotated[bool, Field(description="True si el boton esta presionado")]
    press_count: Annotated[int, Field(default=0, ge=0, description="Contador de pulsaciones")]


# ── Display ────────────────────────────────────────────────────


class DisplayInfo(BaseModel):
    """Informacion del display fisico conectado.

    Attributes:
        connected: True si el display fue detectado e inicializado.
        resolution: Resolucion en formato WxH (ej. '480x320').
        driver: Nombre del driver en uso (ej. 'ili9486', 'piscreen').
    """

    connected: Annotated[bool, Field(description="Display conectado y funcional")]
    resolution: Annotated[
        str,
        Field(pattern=r"^\d+x\d+$", description="Resolucion WxH", examples=["480x320"]),
    ]
    driver: Annotated[str, Field(description="Driver kernel (ili9486, piscreen)", examples=["ili9486"])]


# ── Display Settings (fuente y tamano de texto) ────────────────


class DisplaySettings(BaseModel):
    """Ajustes visuales del display fisico (fuente y tamano de texto).

    Valores acotados a opciones compatibles con una pantalla pequena
    (480x320). Las familias corresponden a fuentes presentes en
    Raspberry Pi OS (DejaVu Sans / Liberation Sans).

    Attributes:
        font_family: Familia tipografica ('dejavu' | 'liberation').
        text_size: Escala del texto ('small' | 'medium' | 'large').
    """

    font_family: Annotated[
        Literal["dejavu", "liberation"],
        Field(default="dejavu", description="Familia tipografica"),
    ]
    text_size: Annotated[
        Literal["small", "medium", "large"],
        Field(default="medium", description="Escala del texto"),
    ]


class DisplayCommand(BaseModel):
    """Comando de cambio de vista enviado al display fisico."""

    action: Annotated[
        Literal["screen_test", "touch_calib", "network", "font", "config", "main"],
        Field(description="Vista a mostrar en el display fisico"),
    ]


# ── System Status ──────────────────────────────────────────────


class SystemStatus(BaseModel):
    """Estado completo del sistema.

    Agrega todos los subsistemas (LED, boton, display) mas metadatos
    del runtime: uptime, temperatura, clientes conectados.

    Attributes:
        led: Estado del LED.
        button: Estado del boton.
        display: Info del display fisico (None si no conectado).
        uptime_seconds: Segundos desde el arranque del servicio.
        cpu_temp_celsius: Temperatura de la CPU en grados Celsius (None si no disponible).
        websocket_clients: Numero de clientes WebSocket conectados.
        timestamp: Momento de generacion del status (UTC).
    """

    led: Annotated[LedState, Field(description="Estado del LED")]
    button: Annotated[ButtonState, Field(description="Estado del boton")]
    display: Annotated[DisplayInfo | None, Field(description="Display fisico (None si no detectado)")]
    uptime_seconds: Annotated[float, Field(description="Segundos desde arranque")]
    cpu_temp_celsius: Annotated[float | None, Field(description="Temperatura CPU en Celsius")]
    websocket_clients: Annotated[int, Field(default=0, ge=0, description="Clientes WS conectados")]
    timestamp: Annotated[datetime, Field(description="Timestamp UTC")]

    @classmethod
    def from_manager(
        cls,
        led: LedState,
        button: ButtonState,
        display: DisplayInfo | None,
        ws_count: int,
        uptime_seconds: float,
    ) -> SystemStatus:
        """Factory method desde los componentes individuales.

        Args:
            led: Estado del LED desde StateManager.
            button: Estado del boton desde StateManager.
            display: Info del display o None.
            ws_count: Clientes WebSocket activos (unicos).
            uptime_seconds: Segundos desde el arranque del servicio.

        Returns:
            SystemStatus con timestamp UTC actual.
        """
        return cls(
            led=led,
            button=button,
            display=display,
            uptime_seconds=uptime_seconds,
            cpu_temp_celsius=cls._read_cpu_temp(),
            websocket_clients=ws_count,
            timestamp=datetime.now(UTC),
        )

    @staticmethod
    def _read_cpu_temp() -> float | None:
        """Lee la temperatura de la CPU desde sysfs.

        Returns:
            Temperatura en grados Celsius, o None si el archivo no existe.
        """
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return float(f.read().strip()) / 1000.0
        except (OSError, FileNotFoundError):
            return None
