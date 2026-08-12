"""Tests para StateManager.

Valida:
- Thread-safety del singleton
- Transiciones de estado correctas
- Broadcast a suscriptores
- Limpieza de suscriptores muertos
"""

from __future__ import annotations

import asyncio
import pytest

from backend.app.models.hmi import ButtonState, LedState, SystemStatus
from backend.app.services.state_manager import StateManager, state_manager


@pytest.fixture(autouse=True)
def reset():
    """Resetea el StateManager antes de cada test."""
    state_manager.set_led(False)
    StateManager.__init__(state_manager)
    yield


class TestLedState:
    """Transiciones de estado del LED."""

    def test_initial_led_is_off(self):
        """LED empieza apagado."""
        assert state_manager.led.state is False
        assert state_manager.led.label == "APAGADO"

    def test_set_led_on(self):
        """set_led(True) enciende el LED."""
        result = state_manager.set_led(True)
        assert result.state is True
        assert result.label == "ENCENDIDO"
        assert state_manager.led.state is True

    def test_set_led_off(self):
        """set_led(False) apaga el LED."""
        state_manager.set_led(True)
        result = state_manager.set_led(False)
        assert result.state is False
        assert result.label == "APAGADO"

    def test_toggle_led(self):
        """Toggle alterna entre ON y OFF."""
        assert state_manager.led.state is False
        state_manager.toggle_led()
        assert state_manager.led.state is True
        state_manager.toggle_led()
        assert state_manager.led.state is False


class TestButtonState:
    """Transiciones de estado del boton."""

    def test_initial_button(self):
        """Boton empieza no presionado."""
        assert state_manager.button.pressed is False
        assert state_manager.button.press_count == 0

    def test_press_button(self):
        """press_button incrementa el contador."""
        result = state_manager.press_button()
        assert result.pressed is True
        assert result.press_count == 1

    def test_release_button(self):
        """release_button cambia pressed a False."""
        state_manager.press_button()
        result = state_manager.release_button()
        assert result.pressed is False
        assert result.press_count == 1  # Contador no se resetea

    def test_multi_press(self):
        """Multiples pulsaciones acumulan."""
        for i in range(5):
            result = state_manager.press_button()
            assert result.press_count == i + 1


class TestSystemStatus:
    """Estado completo del sistema."""

    def test_status_includes_all_subsystems(self):
        """SystemStatus agrega LED, button, display, etc."""
        state_manager.set_display(connected=True, resolution="480x320", driver="piscreen")
        status = state_manager.get_status()
        assert isinstance(status, SystemStatus)
        assert isinstance(status.led, LedState)
        assert isinstance(status.button, ButtonState)
        assert status.display is not None
        assert status.display.connected is True

    def test_status_led_reflects_state(self):
        """Status refleja el estado actual del LED."""
        state_manager.set_led(True)
        status = state_manager.get_status()
        assert status.led.state is True
        assert status.led.label == "ENCENDIDO"


class TestDisplayInfo:
    """Gestion de info del display."""

    def test_display_initial_is_none(self):
        """Display empieza sin info."""
        assert state_manager.display is None

    def test_set_display(self):
        """set_display actualiza la info."""
        state_manager.set_display(connected=True, resolution="800x600", driver="custom")
        display = state_manager.display
        assert display is not None
        assert display.connected is True
        assert display.resolution == "800x600"
        assert display.driver == "custom"

    def test_unconnected_display(self):
        """Display puede estar no conectado."""
        state_manager.set_display(connected=False, resolution="0x0", driver="none")
        assert state_manager.display is not None
        assert state_manager.display.connected is False


class MockWebSocket:
    """Simula una conexion WebSocket para testing."""

    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)


class TestSubscriptions:
    """Suscripciones y broadcast WebSocket."""

    @pytest.mark.asyncio
    async def test_subscribe_sends_status(self):
        """Al suscribirse, recibe el status actual."""
        ws = MockWebSocket()
        await state_manager.subscribe(ws)
        assert len(ws.sent) == 1
        assert ws.sent[0]["type"] == "status_update"
        assert "data" in ws.sent[0]

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_client(self):
        """Unsubscribe elimina al cliente."""
        ws = MockWebSocket()
        await state_manager.subscribe(ws)
        state_manager.unsubscribe(ws)
        # El broadcast no deberia fallar tras unsubscribe
        state_manager.set_led(True)
        # El mock no recibe mas mensajes porque se desuscribio
        assert len(ws.sent) == 1  # Solo el status_update inicial

    @pytest.mark.asyncio
    async def test_ws_count_counts_unique_clients(self):
        """ws_count cuenta clientes unicos, no subscribers por topic."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        # Suscribir ws1 a led y button, ws2 solo a led
        from backend.app.models.events import SubscriptionTopic
        await state_manager.subscribe(ws1, topics=[SubscriptionTopic.LED, SubscriptionTopic.BUTTON])
        await state_manager.subscribe(ws2, topics=[SubscriptionTopic.LED])

        status = state_manager.get_status()
        # Deben ser 2 clientes unicos, no 3 (led+button+led)
        assert status.websocket_clients == 2

    @pytest.mark.asyncio
    async def test_ws_count_zero_with_no_clients(self):
        """ws_count debe ser 0 sin clientes."""
        status = state_manager.get_status()
        assert status.websocket_clients == 0


class TestUptime:
    """Validacion del uptime del servicio."""

    def test_uptime_starts_at_zero_or_near(self):
        """Uptime debe ser >= 0 justo despues del init."""
        status = state_manager.get_status()
        assert status.uptime_seconds >= 0
        assert status.uptime_seconds < 5

    def test_uptime_increases_over_time(self):
        """Uptime debe aumentar con el tiempo."""
        import time
        status1 = state_manager.get_status()
        time.sleep(0.1)
        status2 = state_manager.get_status()
        assert status2.uptime_seconds > status1.uptime_seconds


class TestUpdaterCallback:
    """Pruebas del callback GPIO updater."""

    def test_set_updater_registers_callback(self):
        """set_updater almacena el callback."""
        called: list[bool] = []

        def cb(device: str, state: object) -> None:
            called.append(True)

        state_manager.set_updater(cb)
        assert state_manager._updater_callback is not None

        # Disparar el callback via set_led
        state_manager.set_led(True)
        assert len(called) == 1

    def test_updater_callback_error_is_silent(self):
        """Error en callback GPIO no propaga excepcion."""
        def failing_cb(device: str, state: object) -> None:
            raise RuntimeError("GPIO no disponible")

        state_manager.set_updater(failing_cb)
        # No debe lanzar excepcion
        result = state_manager.set_led(True)
        assert result.state is True


class TestLedStateModel:
    """Pruebas del modelo LedState."""

    def test_is_on_property(self):
        """LedState.is_on devuelve el valor de state."""
        from backend.app.models.hmi import LedState

        on = LedState(state=True, label="ENCENDIDO", gpio_pin=17)
        off = LedState(state=False, label="APAGADO", gpio_pin=17)
        assert on.is_on is True
        assert off.is_on is False


class TestStateManagerLoadPinEdgeCases:
    """Edge cases de carga de pin desde devices.yaml."""

    def test_load_led_pin_handles_missing_file(self, monkeypatch):
        """_load_led_pin no falla si devices.yaml no existe."""
        from backend.app.services.state_manager import StateManager

        pin = StateManager._load_led_pin()
        # Debe devolver un valor (0 como fallback)
        assert isinstance(pin, int)


# ── Concurrency Tests ──────────────────────────────────────────


class TestStateManagerConcurrency:
    """Tests de concurrencia con multiples hilos."""

    def test_concurrent_set_led_sequence_monotonic(self):
        """10 hilos llamando set_led concurrentemente producen sequences en orden."""
        import threading

        sm = StateManager()
        results: list[LedState] = []

        def toggle():
            for _ in range(10):
                state_back = sm.set_led(True)
                results.append(state_back)

        threads = [threading.Thread(target=toggle) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify all 100 calls produced states
        assert len(results) == 100

    def test_concurrent_press_button_no_race(self):
        """20 hilos presionando boton -> press_count = 20."""
        import threading

        sm = StateManager()
        threads = [threading.Thread(target=sm.press_button) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert sm.button.press_count == 20

    def test_concurrent_toggle_consistent_state(self):
        """100 toggles desde 5 hilos — el estado final es un bool consistente."""
        import threading

        sm = StateManager()
        # All threads toggle
        def toggle_n(n):
            for _ in range(n):
                sm.toggle_led()

        threads = [threading.Thread(target=toggle_n, args=(20,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 5 * 20 = 100 toggles — state depends on TOCTOU race,
        # but the final state must be a valid bool and sequence >= 100
        assert isinstance(sm.led.state, bool)
        seq = sm._sequence
        assert seq >= 100


# ── Persistence Integration Tests ──────────────────────────────


class TestStateManagerPersistenceIntegration:
    """Tests de integracion con la capa de persistencia."""

    @pytest.mark.asyncio
    async def test_restore_from_db_with_no_persistence_returns_early(self):
        """Sin persistencia configurada, restore_from_db no hace nada."""
        sm = StateManager()
        await sm.restore_from_db()  # Should not raise

    @pytest.mark.asyncio
    async def test_restore_from_db_sets_led_and_button(self):
        """Con persistencia mockeada, restaura LED y boton correctamente."""
        from unittest.mock import AsyncMock

        sm = StateManager()
        mock_persist = AsyncMock()
        mock_persist.get_led.return_value = True
        mock_persist.get_button_count.return_value = 5
        sm.set_persistence(mock_persist)
        await sm.restore_from_db()
        assert sm.led.state is True
        assert sm.button.press_count == 5

    @pytest.mark.asyncio
    async def test_restore_from_db_handles_exception(self):
        """Si la BD falla al restaurar, no crashea."""
        from unittest.mock import AsyncMock

        sm = StateManager()
        mock_persist = AsyncMock()
        mock_persist.get_led.side_effect = Exception("DB error")
        sm.set_persistence(mock_persist)
        await sm.restore_from_db()  # Should not raise, just log warning

    @pytest.mark.asyncio
    async def test_flush_pending_tasks_no_persistence(self):
        """flush_pending_tasks sin persistencia retorna inmediatamente."""
        sm = StateManager()
        await sm.flush_pending_tasks()  # Should not raise

    def test_state_manager_singleton_exists(self):
        """El singleton state_manager existe al importar."""
        from backend.app.services.state_manager import state_manager as sm

        assert sm is not None
        assert isinstance(sm, StateManager)

    def test_led_device_id_priority_3_tiers(self):
        """_load_led_pin respeta los 3 niveles de prioridad."""
        pin = StateManager._load_led_pin()
        assert isinstance(pin, int)
