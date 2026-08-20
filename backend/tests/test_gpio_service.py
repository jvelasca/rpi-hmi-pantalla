"""Tests para GPIOService.

Valida:
- Deteccion automatica de entorno (real vs mock)
- Configuracion de pines
- Transiciones HIGH/LOW
- Cleanup
"""

from __future__ import annotations

from backend.app.services.gpio_service import (
    GPIOService,
    MockGPIODriver,
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


# ═══════════════════════════════════════════════════════════════
# GPIOService Errors (FASE P1+P2)
# ═══════════════════════════════════════════════════════════════


class TestGPIOServiceErrors:
    """Tests de manejo de errores en GPIOService."""

    def test_real_driver_detection_with_gpiomem(self) -> None:
        """Simula que /dev/gpiomem existe -> detecta RealGPIODriver."""
        from unittest.mock import patch

        from backend.app.services.gpio_service import GPIOService

        with patch("os.path.exists", return_value=True):
            service = GPIOService()
            driver = service._detect_driver()
            assert driver is not None

    def test_gpio_service_cleanup_handles_exception(self) -> None:
        """cleanup no propaga excepciones del driver."""
        from unittest.mock import patch

        from backend.app.services.gpio_service import GPIOService, MockGPIODriver

        service = GPIOService(driver=MockGPIODriver())
        service.setup_output(17)

        with patch.object(service._driver, "cleanup", side_effect=Exception("Mock cleanup error")):
            service.cleanup()
            # No debe propagar la excepcion

    def test_mock_driver_set_high_without_setup(self) -> None:
        """set_high sin setup_output no crashea (warn + no-op)."""
        from backend.app.services.gpio_service import MockGPIODriver

        driver = MockGPIODriver()
        # set_high without setup — should warn but not crash
        driver.set_high(17)
        # MockGPIODriver tracks state anyway
        assert driver._states.get(17) is True
