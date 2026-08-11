"""
backend.app.hardware.hal
========================

Interfaz mínima de abstracción de hardware (HAL).

Contiene:
- definiciones de Device (dataclass)
- interfaz abstracta GPIODriver
- implementación MockGPIODriver para desarrollo
- un stub RealGPIODriver donde se implementará libgpiod/lgpio más adelante
- loader de devices desde YAML (device registry)

El objetivo es que el resto de la aplicación nunca haga referencia a
un pin físico: siempre trabaje con dispositivos declarados en YAML.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any
from abc import ABC, abstractmethod
import yaml
import logging

logger = logging.getLogger("backend.hardware")


@dataclass
class Device:
    """Representación genérica de un dispositivo.

    Campos:
    - id: identificador único (string)
    - name: nombre legible
    - type: tipo lógico (led, relay, sensor...)
    - config: configuración arbitraria cargada desde YAML
    """

    id: str
    name: str
    type: str
    config: Dict[str, Any]


class GPIODriver(ABC):
    """Interfaz abstracta para control GPIO.

    Implementaciones concretas:
    - MockGPIODriver para desarrollo en PC
    - RealGPIODriver para la Raspberry Pi usando libgpiod/lgpio
    """

    @abstractmethod
    def setup_output(self, pin: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_high(self, pin: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def set_low(self, pin: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def cleanup(self) -> None:
        raise NotImplementedError


class MockGPIODriver(GPIODriver):
    """Driver mock que no toca hardware. Usado en CI y desarrollo.

    Guarda el estado de los pines en un diccionario para poder ser
    inspeccionado por tests y scripts de diagnóstico.
    """

    def __init__(self) -> None:
        self.state: Dict[int, bool] = {}
        logger.info("MockGPIODriver inicializado")

    def setup_output(self, pin: int) -> None:
        self.state[pin] = False
        logger.debug("Mock setup pin %s as OUTPUT", pin)

    def set_high(self, pin: int) -> None:
        self.state[pin] = True
        logger.info("Mock pin %s -> HIGH", pin)

    def set_low(self, pin: int) -> None:
        self.state[pin] = False
        logger.info("Mock pin %s -> LOW", pin)

    def cleanup(self) -> None:
        logger.info("Mock driver cleanup called")
        self.state.clear()


class RealGPIODriver(GPIODriver):
    """Stub para un driver real basado en libgpiod o lgpio.

    No implementar aquí cambios de paquetes o instalaciones. Esta clase
    actúa de marcador de posición e indicará en la documentación que
    la implementación deberá usar libgpiod (ej. python-libgpiod) y
    manejar permisos (udev) correctamente.
    """

    def __init__(self) -> None:
        logger.debug("RealGPIODriver instanciado (stub)")
        raise NotImplementedError("RealGPIODriver aún no implementado. Use MockGPIODriver para desarrollo")


def load_devices(path: str) -> Dict[str, Device]:
    """Carga el registro de dispositivos desde un fichero YAML.

    El formato esperado es:

    devices:
      led1:
        name: "LED 1"
        driver: gpio
        pin: 17

    Devuelve un diccionario id -> Device.
    """
    logger.info("Cargando devices desde %s", path)
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    devices: Dict[str, Device] = {}
    for dev_id, cfg in (data.get("devices") or {}).items():
        devices[dev_id] = Device(id=dev_id, name=cfg.get("name", dev_id), type=cfg.get("driver", "unknown"), config=cfg)

    logger.info("Dispositivos cargados: %s", list(devices.keys()))
    return devices
