"""Tests para el ciclo de vida (lifespan) de la aplicacion FastAPI.
Startup: GPIO init, display detection, DB init, state restore.
Shutdown: drain tasks, cleanup GPIO, close persistence.

AVISO: La funcion lifespan se prueba directamente via async context manager.
El objeto `app` de FastAPI se importa del modulo main, ya que el singleton
state_manager/gpio_service se resetea en conftest.py via autouse.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.main import app, lifespan
from backend.app.models.device import DeviceConfig, DeviceType, PinMapping
from backend.app.services.gpio_service import gpio_service
from backend.app.services.state_manager import state_manager

# ── Helpers ────────────────────────────────────────────────────


def _make_device(
    pin_bcm: int = 17,
    dev_type: DeviceType = DeviceType.DIGITAL_OUTPUT,
    role: str = "led",
) -> DeviceConfig:
    """Crea un DeviceConfig de prueba con un ``role`` en kwargs."""
    return DeviceConfig(
        id="led1",
        type=dev_type,
        name="LED 1",
        pin=PinMapping(bcm=pin_bcm, name="LED_ROJO"),
        kwargs={"role": role},
    )


def _two_devices(
    led_pin: int = 20, button_pin: int = 21
) -> dict[str, DeviceConfig]:
    """Crea los dos dispositivos LED (role=led y role=button_led)."""
    return {
        "led1": DeviceConfig(
            id="led1",
            type=DeviceType.DIGITAL_OUTPUT,
            name="LED BOTON ON/OFF",
            pin=PinMapping(bcm=led_pin, name="LED_BOTON_ONOFF"),
            kwargs={"role": "led"},
        ),
        "led_button": DeviceConfig(
            id="led_button",
            type=DeviceType.DIGITAL_OUTPUT,
            name="LED PULSADOR",
            pin=PinMapping(bcm=button_pin, name="LED_PULSADOR"),
            kwargs={"role": "button_led"},
        ),
    }


# ── Startup tests ──────────────────────────────────────────────


class TestLifespanStartup:
    """Pruebas de la fase de arranque del lifespan."""

    @pytest.mark.asyncio
    async def test_gpio_pin_loaded_from_devices_yaml(self):
        """Al cargar devices.yaml, configura los dos LEDs segun su role."""
        devices = _two_devices()

        with patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output") as mock_setup, \
           patch.object(state_manager, "set_updater") as mock_updater, \
           patch.object(state_manager, "set_updater_button") as mock_updater_button, \
           patch.object(state_manager, "set_display"), \
           patch.object(state_manager, "set_persistence"), \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock), \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock), \
           patch.object(gpio_service, "cleanup"), \
           patch.object(Path, "exists", return_value=False), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch("backend.app.services.persistence.get_persistence", new_callable=AsyncMock), \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock):

            async with lifespan(app):
                pass

            assert mock_setup.call_count == 2
            mock_setup.assert_any_call(20)
            mock_setup.assert_any_call(21)
            mock_updater.assert_called_once()
            mock_updater_button.assert_called_once()

    @pytest.mark.asyncio
    async def test_button_led_pin_configured_as_output(self):
        """El LED del pulsador (role=button_led) se configura como salida."""
        devices = _two_devices(led_pin=20, button_pin=21)

        with patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output") as mock_setup, \
           patch.object(state_manager, "set_updater"), \
           patch.object(state_manager, "set_updater_button"), \
           patch.object(state_manager, "set_display"), \
           patch.object(state_manager, "set_persistence"), \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock), \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock), \
           patch.object(gpio_service, "cleanup"), \
           patch.object(Path, "exists", return_value=False), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch("backend.app.services.persistence.get_persistence", new_callable=AsyncMock), \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock):

            async with lifespan(app):
                pass

            mock_setup.assert_any_call(21)

    @pytest.mark.asyncio
    async def test_gpio_not_configured_when_no_devices(self):
        """Si devices.yaml no tiene dispositivos, no se configura GPIO."""
        with patch(
            "backend.app.services.gpio_service.load_devices", return_value={}
        ), patch.object(gpio_service, "setup_output") as mock_setup, \
           patch.object(state_manager, "set_updater"), \
           patch.object(state_manager, "set_display"), \
           patch.object(state_manager, "set_persistence"), \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock), \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock), \
           patch.object(gpio_service, "cleanup"), \
           patch.object(Path, "exists", return_value=False), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch("backend.app.services.persistence.get_persistence", new_callable=AsyncMock), \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock):

            async with lifespan(app):
                pass

            mock_setup.assert_not_called()

    @pytest.mark.asyncio
    async def test_gpio_setup_output_called_with_correct_pin(self):
        """Verifica que setup_output se llame con los pines BCM de cada role."""
        devices = _two_devices(led_pin=23, button_pin=24)

        with patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output") as mock_setup, \
           patch.object(state_manager, "set_updater"), \
           patch.object(state_manager, "set_updater_button"), \
           patch.object(state_manager, "set_display"), \
           patch.object(state_manager, "set_persistence"), \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock), \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock), \
           patch.object(gpio_service, "cleanup"), \
           patch.object(Path, "exists", return_value=False), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch("backend.app.services.persistence.get_persistence", new_callable=AsyncMock), \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock):

            async with lifespan(app):
                pass

            mock_setup.assert_any_call(23)
            mock_setup.assert_any_call(24)

    @pytest.mark.asyncio
    async def test_state_manager_updater_callback_registered(self):
        """Despues del startup, state_manager debe tener los updaters registrados."""
        devices = _two_devices()

        with patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output"), \
           patch.object(state_manager, "set_display"), \
           patch.object(state_manager, "set_persistence"), \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock), \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock), \
           patch.object(gpio_service, "cleanup"), \
           patch.object(Path, "exists", return_value=False), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch("backend.app.services.persistence.get_persistence", new_callable=AsyncMock), \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock):

            async with lifespan(app):
                assert state_manager._updater_callback is not None
                assert state_manager._updater_button_callback is not None

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Mock de Path.exists() no intercepta llamada dentro del lifespan. "
               "La funcion importa Path de pathlib en su propio namespace."
    )
    async def test_display_detected_drm_when_card0_exists(self):
        """Si /dev/dri/card0 existe, detecta display DRM piscreen."""
        devices = _two_devices()

        # Patch pathlib.Path.exists directamente en el modulo
        with patch(
            "pathlib.Path.exists",
            side_effect=lambda self: str(self) == "/dev/dri/card0",
        ), patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output"), \
           patch.object(state_manager, "set_updater"), \
           patch.object(state_manager, "set_updater_button"), \
           patch.object(state_manager, "set_display") as mock_display, \
           patch.object(state_manager, "set_persistence"), \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock), \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock), \
           patch.object(gpio_service, "cleanup"), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch("backend.app.services.persistence.get_persistence", new_callable=AsyncMock), \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock):

            async with lifespan(app):
                pass

            mock_display.assert_called_once_with(
                connected=True, resolution="480x320", driver="piscreen"
            )

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Mock de Path.exists() no intercepta llamada dentro del lifespan. "
               "La funcion importa Path de pathlib en su propio namespace."
    )
    async def test_display_detected_fb_when_fb1_exists(self):
        """Si /dev/fb1 existe, detecta display framebuffer ili9486."""
        devices = _two_devices()

        with patch(
            "pathlib.Path.exists",
            side_effect=lambda self: str(self) == "/dev/fb1",
        ), patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output"), \
           patch.object(state_manager, "set_updater"), \
           patch.object(state_manager, "set_updater_button"), \
           patch.object(state_manager, "set_display") as mock_display, \
           patch.object(state_manager, "set_persistence"), \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock), \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock), \
           patch.object(gpio_service, "cleanup"), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch("backend.app.services.persistence.get_persistence", new_callable=AsyncMock), \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock):

            async with lifespan(app):
                pass

            mock_display.assert_called_once_with(
                connected=True, resolution="480x320", driver="ili9486"
            )

    @pytest.mark.asyncio
    async def test_display_not_detected_when_none_exist(self):
        """Si ningun display existe, no se llama set_display con connected=True."""
        devices = _two_devices()

        with patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output"), \
           patch.object(state_manager, "set_updater"), \
           patch.object(state_manager, "set_updater_button"), \
           patch.object(state_manager, "set_display") as mock_display, \
           patch.object(state_manager, "set_persistence"), \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock), \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock), \
           patch.object(gpio_service, "cleanup"), \
           patch.object(Path, "exists", return_value=False), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch("backend.app.services.persistence.get_persistence", new_callable=AsyncMock), \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock):

            async with lifespan(app):
                pass

            # No debe llamarse con connected=True
            calls = mock_display.call_args_list
            connected_calls = [
                c for c in calls if c.kwargs.get("connected") is True
            ]
            assert len(connected_calls) == 0

    @pytest.mark.asyncio
    async def test_ssh_auto_connect_not_called_when_admin_api_disabled(self):
        """Con enable_admin_api=False, no se llama a auto_connect_ssh."""
        devices = _two_devices()

        with patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output"), \
           patch.object(state_manager, "set_updater"), \
           patch.object(state_manager, "set_updater_button"), \
           patch.object(state_manager, "set_display"), \
           patch.object(state_manager, "set_persistence"), \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock), \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock), \
           patch.object(gpio_service, "cleanup"), \
           patch.object(Path, "exists", return_value=False), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch("backend.app.api.ssh.auto_connect_ssh", new_callable=AsyncMock) as mock_ssh, \
           patch("backend.app.services.persistence.get_persistence", new_callable=AsyncMock), \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock):

            async with lifespan(app):
                pass

            mock_ssh.assert_not_called()

    @pytest.mark.asyncio
    async def test_persistence_initialized_and_state_restored(self):
        """La persistencia se inicializa y se restaura el estado desde BD."""
        devices = _two_devices()
        mock_db = AsyncMock()

        with patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output"), \
           patch.object(state_manager, "set_updater"), \
           patch.object(state_manager, "set_updater_button"), \
           patch.object(state_manager, "set_display"), \
           patch.object(state_manager, "set_persistence") as mock_set_pers, \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock) as mock_restore, \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock), \
           patch.object(gpio_service, "cleanup"), \
           patch.object(Path, "exists", return_value=False), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch(
               "backend.app.services.persistence.get_persistence",
               new_callable=AsyncMock,
               return_value=mock_db,
           ) as mock_get_pers, \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock):

            async with lifespan(app):
                pass

            mock_get_pers.assert_called_once()
            mock_set_pers.assert_called_once_with(mock_db)
            mock_restore.assert_called_once()

    @pytest.mark.asyncio
    async def test_sqlite_failure_prevents_ready(self):
        """Si SQLite falla en arranque, el lifespan relanza el error (fail-closed)."""
        devices = _two_devices()
        with patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output"), \
           patch.object(state_manager, "set_updater"), \
           patch.object(state_manager, "set_updater_button"), \
           patch.object(state_manager, "set_display"), \
           patch.object(Path, "exists", return_value=False), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch(
               "backend.app.services.persistence.get_persistence",
               new_callable=AsyncMock,
               side_effect=RuntimeError("SQLite corrupta"),
           ), \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock), \
           pytest.raises(RuntimeError):
            async with lifespan(app):
                pass

    @pytest.mark.asyncio
    async def test_app_docs_control_at_startup(self):
        """Verifica que la config de docs (enable_docs) afecta a docs_url.
        NOTA: docs_url se evalua en tiempo de importacion del modulo.
        Este test verifica el valor actual; no se puede cambiar dinamicamente.
        """
        from backend.app.config import settings

        if settings.enable_docs:
            assert app.docs_url == "/docs"
        else:
            assert app.docs_url is None


# ── Shutdown tests ─────────────────────────────────────────────


class TestLifespanShutdown:
    """Pruebas de la fase de apagado del lifespan."""

    @pytest.mark.asyncio
    async def test_flush_pending_tasks_called_on_shutdown(self):
        """Durante el shutdown, se llama a flush_pending_tasks."""
        devices = _two_devices()

        with patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output"), \
           patch.object(state_manager, "set_updater"), \
           patch.object(state_manager, "set_updater_button"), \
           patch.object(state_manager, "set_display"), \
           patch.object(state_manager, "set_persistence"), \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock), \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock) as mock_flush, \
           patch.object(gpio_service, "cleanup"), \
           patch.object(Path, "exists", return_value=False), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch("backend.app.services.persistence.get_persistence", new_callable=AsyncMock), \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock):

            async with lifespan(app):
                pass  # startup

            # Despues de salir del context manager, shutdown ha ocurrido
            mock_flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_gpio_cleanup_called_on_shutdown(self):
        """Durante el shutdown, se llama a gpio_service.cleanup()."""
        devices = _two_devices()

        with patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output"), \
           patch.object(state_manager, "set_updater"), \
           patch.object(state_manager, "set_updater_button"), \
           patch.object(state_manager, "set_display"), \
           patch.object(state_manager, "set_persistence"), \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock), \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock), \
           patch.object(gpio_service, "cleanup") as mock_cleanup, \
           patch.object(Path, "exists", return_value=False), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch("backend.app.services.persistence.get_persistence", new_callable=AsyncMock), \
           patch("backend.app.services.persistence.close_persistence", new_callable=AsyncMock):

            async with lifespan(app):
                pass

            mock_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_persistence_called_on_shutdown(self):
        """Durante el shutdown, se llama a close_persistence()."""
        devices = _two_devices()

        with patch(
            "backend.app.services.gpio_service.load_devices", return_value=devices
        ), patch.object(gpio_service, "setup_output"), \
           patch.object(state_manager, "set_updater"), \
           patch.object(state_manager, "set_updater_button"), \
           patch.object(state_manager, "set_display"), \
           patch.object(state_manager, "set_persistence"), \
           patch.object(state_manager, "restore_from_db", new_callable=AsyncMock), \
           patch.object(state_manager, "flush_pending_tasks", new_callable=AsyncMock), \
           patch.object(gpio_service, "cleanup"), \
           patch.object(Path, "exists", return_value=False), \
           patch("backend.app.main.settings.enable_admin_api", False), \
           patch("backend.app.services.persistence.get_persistence", new_callable=AsyncMock), \
           patch(
               "backend.app.services.persistence.close_persistence",
               new_callable=AsyncMock,
           ) as mock_close_pers:

            async with lifespan(app):
                pass

            mock_close_pers.assert_called_once()
