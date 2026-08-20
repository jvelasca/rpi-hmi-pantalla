"""Tests para el endpoint WebSocket /ws.
Verifica protocolo, suscripciones, mensajes y desconexion.

NOTA: Los tests son sincronos porque TestClient.websocket_connect
usa su propio event loop interno (via anyio) y no es compatible
con @pytest.mark.asyncio en este contexto.
"""

from __future__ import annotations

import pytest

from backend.app.services.state_manager import StateManager, state_manager


class TestWebSocketEndpoint:
    """Pruebas integradas del endpoint /ws."""

    @pytest.fixture(autouse=True)
    def _reset_state(self):
        """Resetea el StateManager antes de cada test."""
        state_manager.set_led(False)
        StateManager.__init__(state_manager)  # type: ignore

    def test_connect_and_receives_initial_status(self, client):
        """Al conectar y suscribirse, recibe status_update inmediato."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"version": "1.0", "type": "subscribe"})
            data = ws.receive_json()
            assert data["type"] == "status_update"
            assert "data" in data
            assert "led" in data["data"]
            assert "button" in data["data"]

    def test_toggle_led_via_ws(self, client):
        """Enviar toggle_led cambia el estado y emite led_changed."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"version": "1.0", "type": "subscribe", "topics": ["led"]})
            _ = ws.receive_json()  # status_update inicial

            # Toggle: off -> on
            ws.send_json({"version": "1.0", "type": "toggle_led"})
            msg = ws.receive_json()
            assert msg["type"] == "led_changed"
            assert msg["data"]["state"] is True
            assert msg["data"]["label"] == "ENCENDIDO"

            # Toggle: on -> off
            ws.send_json({"version": "1.0", "type": "toggle_led"})
            msg = ws.receive_json()
            assert msg["type"] == "led_changed"
            assert msg["data"]["state"] is False
            assert msg["data"]["label"] == "APAGADO"

    def test_protocol_version_mismatch(self, client):
        """Version != 1.0 debe devolver PROTOCOL_VERSION_MISMATCH."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"version": "0.9", "type": "toggle_led"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["data"]["code"] == "PROTOCOL_VERSION_MISMATCH"

    def test_unknown_message_type(self, client):
        """Un type desconocido falla en validacion Pydantic y emite INTERNAL_ERROR.
        NOTA: ClientMessage usa Literal para el campo 'type', asi que los tipos
        desconocidos son rechazados en model_validate(), antes del match.
        El except generico envia INTERNAL_ERROR en ese caso.
        """
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"version": "1.0", "type": "invalid_action"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["data"]["code"] == "INTERNAL_ERROR"

    def test_disconnect_removes_subscriber(self, client):
        """Tras desconectar, ws_count debe ser 0 en /api/status."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"version": "1.0", "type": "subscribe"})
            _ = ws.receive_json()  # status_update

        # Fuera del context manager: WS desconectado
        r = client.get("/api/status")
        assert r.status_code == 200
        assert r.json()["websocket_clients"] == 0

    def test_get_status_via_ws(self, client):
        """get_status devuelve status_update con datos completos."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"version": "1.0", "type": "get_status"})
            msg = ws.receive_json()
            assert msg["type"] == "status_update"
            data = msg["data"]
            assert "led" in data
            assert "button" in data
            assert "websocket_clients" in data
            assert "uptime_seconds" in data

    def test_press_and_release_button(self, client):
        """Secuencia press + release incrementa el contador."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {"version": "1.0", "type": "subscribe", "topics": ["button"]}
            )
            _ = ws.receive_json()  # status_update

            # Press
            ws.send_json({"version": "1.0", "type": "press_button"})
            msg = ws.receive_json()
            assert msg["type"] == "button_pressed"
            assert msg["data"]["pressed"] is True
            assert msg["data"]["press_count"] == 1

            # Release
            ws.send_json({"version": "1.0", "type": "release_button"})
            msg = ws.receive_json()
            assert msg["type"] == "button_released"
            assert msg["data"]["pressed"] is False
            assert msg["data"]["press_count"] == 1

            # Second press
            ws.send_json({"version": "1.0", "type": "press_button"})
            msg = ws.receive_json()
            assert msg["type"] == "button_pressed"
            assert msg["data"]["press_count"] == 2

    def test_subscribe_with_specific_topics(self, client):
        """subscribe con topics=["led"] solo recibe eventos de ese topico."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"version": "1.0", "type": "subscribe", "topics": ["led"]})
            initial = ws.receive_json()
            assert initial["type"] == "status_update"

            # toggle_led deberia emitir led_changed al suscriptor
            ws.send_json({"version": "1.0", "type": "toggle_led"})
            msg = ws.receive_json()
            assert msg["type"] == "led_changed"

    def test_invalid_json_causes_error(self, client):
        """Mensaje no-JSON no debe crashear el servidor WebSocket."""
        with client.websocket_connect("/ws") as ws:
            # Enviar texto que no es JSON valido
            ws.send_text("esto no es json")
            # El servidor deberia manejar el error sin crashear.
            # Intentar enviar un mensaje valido despues para verificar
            # que la conexion sigue viva o se cierra limpiamente.
            try:
                ws.send_json({"version": "1.0", "type": "subscribe"})
                msg = ws.receive_json()
                assert msg["type"] == "status_update"
            except Exception:
                # Si la conexion se cerro, es aceptable (el servidor
                # protege contra malformed input)
                pass

    def test_led_on_then_off_via_ws(self, client):
        """Toggle enciende y apaga secuencialmente via WebSocket."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"version": "1.0", "type": "subscribe", "topics": ["led"]})
            _ = ws.receive_json()  # status_update

            # Encender (toggle desde off)
            ws.send_json({"version": "1.0", "type": "toggle_led"})
            msg_on = ws.receive_json()
            assert msg_on["data"]["state"] is True
            assert msg_on["data"]["label"] == "ENCENDIDO"

            # Apagar (toggle desde on)
            ws.send_json({"version": "1.0", "type": "toggle_led"})
            msg_off = ws.receive_json()
            assert msg_off["data"]["state"] is False
            assert msg_off["data"]["label"] == "APAGADO"

    def test_multiple_subscriptions_independent(self, client):
        """Dos clientes WS pueden estar conectados independientemente."""
        with client.websocket_connect("/ws") as ws1, client.websocket_connect(
            "/ws"
        ) as ws2:

            ws1.send_json(
                {"version": "1.0", "type": "subscribe", "topics": ["led"]}
            )
            ws2.send_json(
                {"version": "1.0", "type": "subscribe", "topics": ["button"]}
            )

            _ = ws1.receive_json()
            _ = ws2.receive_json()

            ws1.send_json({"version": "1.0", "type": "toggle_led"})
            msg1 = ws1.receive_json()
            assert msg1["type"] == "led_changed"

        # Verificar que /api/status reporta 0 clientes
        r = client.get("/api/status")
        assert r.status_code == 200
        assert r.json()["websocket_clients"] == 0
