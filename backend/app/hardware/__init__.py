"""Capa de abstraccion de hardware (HAL).

Proporciona interfaces para dispositivos fisicos:
GPIO, I2C, SPI, PWM.
"""

from backend.app.hardware.hal import GPIODriver

__all__ = ["GPIODriver"]
