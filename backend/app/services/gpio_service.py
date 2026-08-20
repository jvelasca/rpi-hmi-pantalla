"""GPIOService — Abstraction del hardware GPIO via gpiozero.

Proporciona una capa unificada para controlar pines GPIO,
con deteccion automatica del entorno:

- En Raspberry Pi: usa gpiozero (LED, Button, etc.)
- En PC/desarrollo: usa MockGPIODriver (simulacion)

Tambien incluye carga declarativa de dispositivos desde YAML
(devices.yaml), fuente unica de verdad para pines y configuracion.

Uso:
    from backend.app.services.gpio_service import gpio_service, load_devices

    gpio_service.setup_output(17)         # Configurar GPIO17 como salida
    gpio_service.set_high(17)             # Encender LED en GPIO17
    gpio_service.set_low(17)              # Apagar LED en GPIO17

    devices = load_devices("backend/config/devices.yaml")
    pin = devices["led1"].pin.bcm if devices["led1"].pin else 0  # Leer pin desde YAML
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict

import yaml  # type: ignore[import-untyped]  # noqa: F401 — retrocompat, sin stubs de PyYAML

from backend.app.models.device import DeviceConfig, load_devices as _load_devices  # noqa: F401

logger = logging.getLogger(__name__)

__all__ = [
    "GPIOService",
    "gpio_service",
    "load_devices",
    "DeviceConfig",
    "MockGPIODriver",
    "RealGPIODriver",
]


def load_devices(path: str) -> Dict[str, DeviceConfig]:
    """Carga el registro de dispositivos desde un fichero YAML.

    Delega en backend.app.models.device.load_devices (modelo Pydantic).

    Args:
        path: Ruta al archivo devices.yaml.

    Returns:
        Diccionario id -> DeviceConfig.
    """
    return _load_devices(path)


# ── Driver Interface ──────────────────────────────────────────


class GPIODriver(ABC):
    """Interfaz abstracta para drivers GPIO."""

    @abstractmethod
    def setup_output(self, pin: int) -> None:
        """Configura un pin como salida digital."""

    @abstractmethod
    def set_high(self, pin: int) -> None:
        """Pone un pin en alto (3.3V)."""

    @abstractmethod
    def set_low(self, pin: int) -> None:
        """Pone un pin en bajo (0V)."""

    @abstractmethod
    def cleanup(self, pin: int) -> None:
        """Libera los recursos del pin."""


class RealGPIODriver(GPIODriver):
    """Driver real usando gpiozero (solo en Raspberry Pi)."""

    def __init__(self) -> None:
        self._leds: dict[int, Any] = {}  # pin -> LED instance

    def setup_output(self, pin: int) -> None:
        from gpiozero import LED

        if pin not in self._leds:
            self._leds[pin] = LED(pin)
            logger.info("GPIO %d configurado como salida (LED)", pin)

    def set_high(self, pin: int) -> None:
        if pin in self._leds:
            self._leds[pin].on()
        else:
            logger.warning("GPIO %d no configurado como salida", pin)

    def set_low(self, pin: int) -> None:
        if pin in self._leds:
            self._leds[pin].off()
        else:
            logger.warning("GPIO %d no configurado como salida", pin)

    def cleanup(self, pin: int) -> None:
        if pin in self._leds:
            self._leds[pin].close()
            del self._leds[pin]
            logger.info("GPIO %d liberado", pin)


class MockGPIODriver(GPIODriver):
    """Driver simulado para desarrollo y testing fuera de la Pi."""

    def __init__(self) -> None:
        self._states: dict[int, bool] = {}

    def setup_output(self, pin: int) -> None:
        self._states.setdefault(pin, False)
        logger.debug("[MOCK] GPIO %d configurado como salida", pin)

    def set_high(self, pin: int) -> None:
        self._states[pin] = True
        logger.debug("[MOCK] GPIO %d -> HIGH", pin)

    def set_low(self, pin: int) -> None:
        self._states[pin] = False
        logger.debug("[MOCK] GPIO %d -> LOW", pin)

    def cleanup(self, pin: int) -> None:
        self._states.pop(pin, None)
        logger.debug("[MOCK] GPIO %d liberado", pin)


# ── Service ───────────────────────────────────────────────────


class GPIOService:
    """Servicio de alto nivel para control de GPIO.

    Selecciona automaticamente el driver real en Raspberry Pi
    o el mock en otros entornos.
    """

    def __init__(self, driver: GPIODriver | None = None) -> None:
        self._driver: GPIODriver = driver or self._detect_driver()
        self._configured_pins: set[int] = set()

    @staticmethod
    def _detect_driver() -> GPIODriver:
        """Detecta el driver adecuado segun el entorno.

        Criterios:
        - /dev/gpiomem existe -> Raspberry Pi real -> RealGPIODriver
        - En caso contrario -> MockGPIODriver

        Returns:
            Instancia de GPIODriver.
        """
        if os.path.exists("/dev/gpiomem") or os.path.exists("/sys/class/gpio"):
            logger.info("Entorno detectado: Raspberry Pi -> RealGPIODriver")
            return RealGPIODriver()
        logger.info("Entorno detectado: PC/desarrollo -> MockGPIODriver")
        return MockGPIODriver()

    def is_real_hardware(self) -> bool:
        """True si se esta usando hardware real."""
        return isinstance(self._driver, RealGPIODriver)

    def setup_output(self, pin: int) -> None:
        """Configura un pin BCM como salida digital.

        Args:
            pin: Numero de pin en notacion BCM (ej. 17).
        """
        self._driver.setup_output(pin)
        self._configured_pins.add(pin)

    def set_state(self, pin: int, state: bool) -> None:
        """Establece el estado de un pin de salida.

        Args:
            pin: Numero de pin BCM.
            state: True = HIGH (3.3V), False = LOW (0V).
        """
        if pin not in self._configured_pins:
            self.setup_output(pin)
        if state:
            self._driver.set_high(pin)
        else:
            self._driver.set_low(pin)

    def cleanup(self) -> None:
        """Libera todos los pines configurados."""
        for pin in list(self._configured_pins):
            try:
                self._driver.cleanup(pin)
            except Exception as exc:
                logger.warning("Error liberando GPIO %d: %s", pin, exc)
        self._configured_pins.clear()
        logger.info("Todos los GPIO liberados")


# ── Singleton ──────────────────────────────────────────────────

gpio_service = GPIOService()
"""Instancia unica global del GPIOService."""
