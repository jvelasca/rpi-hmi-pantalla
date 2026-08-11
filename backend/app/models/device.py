"""Modelos de configuracion de dispositivos hardware.

Define como se registran los dispositivos fisicos (GPIO, I2C, SPI)
en el sistema, usando un archivo YAML declarativo.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field


class DeviceType(StrEnum):
    """Tipos de dispositivos soportados por la HAL."""

    DIGITAL_OUTPUT = "digital_output"  # LED, relay, etc.
    DIGITAL_INPUT = "digital_input"    # Button, switch, etc.
    ANALOG_INPUT = "analog_input"      # ADC via SPI/I2C
    PWM_OUTPUT = "pwm_output"          # Servo, dimmer, etc.
    I2C_DEVICE = "i2c_device"          # Sensor I2C generico
    SPI_DEVICE = "spi_device"          # Dispositivo SPI generico


class PinMapping(BaseModel):
    """Mapeo de pines para un dispositivo.

    Attributes:
        bcm: Numero de pin en numeracion BCM (Broadcom).
        name: Nombre descriptivo (ej. 'LED_ROJO').
    """

    bcm: Annotated[int, Field(ge=2, le=27, description="Pin en numeracion BCM")]
    name: Annotated[str, Field(min_length=1, max_length=32, description="Nombre del pin")]


class DeviceConfig(BaseModel):
    """Configuracion de un dispositivo en el registro YAML.

    Attributes:
        id: Identificador unico (ej. 'led1').
        type: Tipo de dispositivo (digital_output, i2c_device, etc.).
        name: Nombre descriptivo legible.
        pin: Mapeo de pines (None para dispositivos sin GPIO directo).
        kwargs: Parametros adicionales especificos del dispositivo.
    """

    id: Annotated[str, Field(min_length=1, max_length=64, description="ID unico del dispositivo")]
    type: Annotated[DeviceType, Field(description="Tipo de dispositivo")]
    name: Annotated[str, Field(min_length=1, max_length=128, description="Nombre descriptivo")]
    pin: Annotated[PinMapping | None, Field(default=None, description="Mapeo de pines")]
    kwargs: Annotated[dict, Field(default_factory=dict, description="Parametros adicionales")]
