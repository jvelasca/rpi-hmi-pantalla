"""Tests para GPIOService.

Valida:
- Deteccion automatica de entorno (real vs mock)
- Configuracion de pines
- Transiciones HIGH/LOW
- Cleanup
"""

from __future__ import annotations

import pytest

from backend.app.services.gpio_service import (
    GPIOService,
    MockGPIODriver,
    RealGPIODriver,
    gpio_service,
)


class TestMockDriver:
    """Tests del driver simulado."""

    def test_setup_and_set_high(self):
        """Configurar pin y ponerlo en HIGH."""
        driver = MockGPIODriver()
        driver.setup_output(17)
        driver.set_high(17)
        assert driver._states[17] is True

    def test_set_low(self):
        """Poner pin en LOW."""
        driver = MockGPIODriver()
        driver.setup_output(17)
        driver.set_high(17)
        driver.set_low(17)
        assert driver._states[17] is False

    def test_cleanup(self):
        """Cleanup elimina el pin."""
        driver = MockGPIODriver()
        driver.setup_output(17)
        driver.cleanup(17)
        assert 17 not in driver._states

    def test_multiple_pins(self):
        """Multiples pines independientes."""
        driver = MockGPIODriver()
        driver.setup_output(17)
        driver.setup_output(18)
        driver.set_high(17)
        driver.set_low(18)
        assert driver._states[17] is True
        assert driver._states[18] is False


class TestGPIOService:
    """Tests del servicio de alto nivel."""

    def test_is_not_real_hardware(self):
        """En PC, is_real_hardware devuelve False."""
        svc = GPIOService(driver=MockGPIODriver())
        assert svc.is_real_hardware() is False

    def test_set_state_auto_setup(self):
        """set_state configura el pin automaticamente si no existe."""
        svc = GPIOService(driver=MockGPIODriver())
        svc.set_state(17, True)
        assert 17 in svc._configured_pins

    def test_set_state_high_low(self):
        """set_state cambia HIGH/LOW."""
        svc = GPIOService(driver=MockGPIODriver())
        svc.set_state(17, True)
        svc.set_state(17, False)
        # No debe lanzar excepcion

    def test_cleanup_removes_all(self):
        """Cleanup elimina todos los pines."""
        svc = GPIOService(driver=MockGPIODriver())
        svc.setup_output(17)
        svc.setup_output(22)
        svc.cleanup()
        assert len(svc._configured_pins) == 0
