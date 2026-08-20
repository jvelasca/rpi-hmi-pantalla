"""Modelos de configuracion de dispositivos hardware.

Define como se registran los dispositivos fisicos (GPIO, I2C, SPI)
en el sistema, usando un archivo YAML declarativo.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Annotated, Any

import yaml  # type: ignore[import-untyped]  # sin stubs de PyYAML
from pydantic import BaseModel, Field

logger = logging.getLogger("backend.models.device")


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
    kwargs: Annotated[dict[str, Any], Field(default_factory=dict, description="Parametros adicionales")]


def load_devices(path: str) -> dict[str, DeviceConfig]:
    """Carga el registro de dispositivos desde un fichero YAML.

    Formato esperado (Pydantic DeviceConfig):

        devices:
          - id: led1
            type: digital_output
            name: "LED 1"
            pin:
              bcm: 17
              name: "LED_ROJO"

    Tambien acepta el formato antiguo con claves en lugar de lista
    (retrocompatibilidad temporal).

    Args:
        path: Ruta al archivo devices.yaml.

    Returns:
        Diccionario id -> DeviceConfig.
    """
    logger.info("Cargando devices desde %s", path)
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    raw_devices = data.get("devices", [])

    # Si es una lista (nuevo formato Pydantic)
    if isinstance(raw_devices, list):
        result: dict[str, DeviceConfig] = {}
        for item in raw_devices:
            device = DeviceConfig.model_validate(item)
            result[device.id] = device
        logger.info("Dispositivos cargados (formato Pydantic): %s", list(result.keys()))
        return result

    # Retrocompatibilidad con formato antiguo (dict con claves)
    legacy_result: dict[str, DeviceConfig] = {}
    for dev_id, cfg in raw_devices.items():
        legacy_result[dev_id] = _migrate_old_format(dev_id, cfg)
    logger.info("Dispositivos cargados (formato antiguo, migrado): %s", list(legacy_result.keys()))
    return legacy_result


def _migrate_old_format(dev_id: str, cfg: dict[str, Any]) -> DeviceConfig:
    """Convierte una entrada del formato antiguo al nuevo DeviceConfig.

    Formato antiguo:
        led1:
          name: "LED 1"
          driver: "gpio"
          pin: 17
          mode: output

    Args:
        dev_id: ID del dispositivo.
        cfg: Configuracion en formato antiguo.

    Returns:
        DeviceConfig validado con Pydantic.
    """
    driver = cfg.get("driver", "gpio")
    mode = cfg.get("mode", "output")

    # Mapear driver+mode a DeviceType
    if driver == "gpio" and mode == "output":
        dev_type = DeviceType.DIGITAL_OUTPUT
    elif driver == "gpio" and mode == "input":
        dev_type = DeviceType.DIGITAL_INPUT
    elif driver == "i2c":
        dev_type = DeviceType.I2C_DEVICE
    elif driver == "spi":
        dev_type = DeviceType.SPI_DEVICE
    else:
        dev_type = DeviceType.DIGITAL_OUTPUT

    # Construir PinMapping si hay pin
    pin_raw = cfg.get("pin")
    pin = None
    if isinstance(pin_raw, int) and 2 <= pin_raw <= 27:
        pin = PinMapping(bcm=pin_raw, name=f"PIN_{pin_raw}")
    elif isinstance(pin_raw, dict):
        pin = PinMapping(**pin_raw)

    return DeviceConfig(
        id=dev_id,
        type=dev_type,
        name=cfg.get("name", dev_id),
        pin=pin,
        kwargs=cfg.get("kwargs", {}),
    )
