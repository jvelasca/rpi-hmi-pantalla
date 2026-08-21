"""Tests para los endpoints HMI REST.

Valida:
- Todos los endpoints devuelven codigos HTTP correctos
- Los modelos de respuesta son validos
- Las operaciones de toggle son idempotentes
- POST /api/led/on y /api/led/off mutan el estado correctamente
- GET /api/status incluye todos los subsistemas
- En SECURITY_MODE=protected, los mutadores exigen X-API-Key
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import config as config_module
from backend.app.main import app
from backend.app.services.security_manager import security_manager

# ── Health Check ──────────────────────────────────────────────


class TestHealthCheck:
    """Tests de health check."""

    def test_health_returns_ok(self, client):
        """GET /health devuelve HealthStatus con checks."""
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "checks" in data
        assert "api" in data["checks"]
        assert "uptime" in data["checks"]
        assert "timestamp" in data
        assert "uptime_seconds" in data

    async def test_health_async(self, async_client):
        """GET /health via async client."""
        r = await async_client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "checks" in data


# ── LED Endpoints ─────────────────────────────────────────────


class TestLed:
    """Tests del subsistema LED."""

    def test_get_led_initial_state(self, client):
        """LED empieza apagado."""
        r = client.get("/api/led")
        assert r.status_code == 200
        assert r.json()["state"] is False
        assert r.json()["label"] == "APAGADO"

    def test_toggle_led(self, client):
        """Toggle alterna el estado."""
        r = client.post("/api/led/toggle")
        assert r.status_code == 200
        assert r.json()["state"] is True

        r = client.post("/api/led/toggle")
        assert r.status_code == 200
        assert r.json()["state"] is False

    def test_led_on(self, client):
        """POST /api/led/on enciende el LED."""
        client.post("/api/led/toggle")  # asegurar apagado primero
        r = client.post("/api/led/on")
        assert r.status_code == 200
        assert r.json()["state"] is True

    def test_led_off(self, client):
        """POST /api/led/off apaga el LED."""
        client.post("/api/led/on")  # asegurar encendido
        r = client.post("/api/led/off")
        assert r.status_code == 200
        assert r.json()["state"] is False

    def test_led_on_is_idempotent(self, client):
        """Encender dos veces no cambia nada."""
        r1 = client.post("/api/led/on")
        r2 = client.post("/api/led/on")
        assert r1.json() == r2.json()

    def test_led_off_is_idempotent(self, client):
        """Apagar dos veces no cambia nada."""
        r1 = client.post("/api/led/off")
        r2 = client.post("/api/led/off")
        assert r1.json() == r2.json()


# ── Button Endpoints ──────────────────────────────────────────


class TestButton:
    """Tests del subsistema Button."""

    def test_get_button_initial(self, client):
        """Boton empieza no presionado con contador 0."""
        r = client.get("/api/button")
        assert r.status_code == 200
        assert r.json()["pressed"] is False
        assert r.json()["press_count"] == 0

    def test_press_button(self, client):
        """POST /api/button/press incrementa el contador."""
        r = client.post("/api/button/press")
        assert r.status_code == 200
        assert r.json()["pressed"] is True
        assert r.json()["press_count"] == 1

    def test_press_button_toggles_led(self, client):
        """POST /api/button/press tambien alterna el LED."""
        assert client.get("/api/led").json()["state"] is False
        client.post("/api/button/press")
        assert client.get("/api/led").json()["state"] is True
        client.post("/api/button/press")
        assert client.get("/api/led").json()["state"] is False

    def test_button_multi_press(self, client):
        """Multiples pulsaciones incrementan el contador."""
        for i in range(3):
            r = client.post("/api/button/press")
            assert r.json()["press_count"] == i + 1

    def test_release_button(self, client):
        """POST /api/button/release cambia pressed a False."""
        client.post("/api/button/press")
        r = client.post("/api/button/release")
        assert r.status_code == 200
        assert r.json()["pressed"] is False


# ── Status Endpoint ───────────────────────────────────────────


class TestStatus:
    """Tests del endpoint de status."""

    def test_status_returns_all_fields(self, client):
        """Status incluye LED, button, display, timestamp, etc."""
        r = client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert "led" in data
        assert "button" in data
        assert "display" in data
        assert "uptime_seconds" in data
        assert "websocket_clients" in data
        assert "timestamp" in data

    def test_status_reflects_led_change(self, client):
        """Status refleja cambios de estado del LED."""
        client.post("/api/led/on")
        r = client.get("/api/status")
        assert r.json()["led"]["state"] is True
        assert r.json()["led"]["label"] == "ENCENDIDO"


# ── Auth en modo protected ────────────────────────────────────


@pytest.fixture
def protected_mode(monkeypatch):
    """Activa la seguridad del panel con una ADMIN_API_KEY conocida."""
    monkeypatch.setattr(config_module.settings, "security_mode", "protected")
    monkeypatch.setattr(config_module.settings, "admin_api_key", "test-key-123")
    security_manager.reset()  # enabled=True (security_mode=protected) + hash "1234"
    return "test-key-123"


class TestProtectedHmi:
    """Mutadores HMI exigen X-API-Key en SECURITY_MODE=protected."""

    def test_led_on_without_key_returns_401(self, client, protected_mode):
        """POST /api/led/on en protected sin key -> 401."""
        r = client.post("/api/led/on")
        assert r.status_code == 401

    def test_led_on_with_key_returns_200(self, client, protected_mode):
        """POST /api/led/on en protected con key correcta -> 200."""
        r = client.post("/api/led/on", headers={"X-API-Key": protected_mode})
        assert r.status_code == 200
        assert r.json()["state"] is True

    def test_led_on_with_wrong_key_returns_401(self, client, protected_mode):
        """POST /api/led/on en protected con key incorrecta -> 401."""
        r = client.post("/api/led/on", headers={"X-API-Key": "wrong-key"})
        assert r.status_code == 401

    def test_get_led_remains_public_in_protected(self, client, protected_mode):
        """Los GET de solo lectura siguen siendo publicos en protected."""
        r = client.get("/api/led")
        assert r.status_code == 200

    def test_led_on_loopback_without_key_returns_200(self, protected_mode):
        """POST /api/led/on en protected desde loopback -> 200 (display local)."""
        loopback_client = TestClient(app, client=("127.0.0.1", 50000))
        r = loopback_client.post("/api/led/on")
        assert r.status_code == 200
        assert r.json()["state"] is True

    def test_settings_display_protected_without_key_returns_401(self, client, protected_mode):
        """POST /api/settings/display en protected sin key (no-loopback) -> 401."""
        r = client.post(
            "/api/settings/display",
            json={"font_family": "dejavu", "text_size": "medium"},
        )
        assert r.status_code == 401

    def test_settings_display_protected_with_key_returns_200(self, client, protected_mode):
        """POST /api/settings/display en protected con key -> 200."""
        r = client.post(
            "/api/settings/display",
            json={"font_family": "liberation", "text_size": "large"},
            headers={"X-API-Key": protected_mode},
        )
        assert r.status_code == 200
        assert r.json()["font_family"] == "liberation"

    def test_settings_display_loopback_without_key_returns_200(self, protected_mode):
        """POST /api/settings/display en protected desde loopback -> 200."""
        loopback_client = TestClient(app, client=("127.0.0.1", 50000))
        r = loopback_client.post(
            "/api/settings/display",
            json={"font_family": "dejavu", "text_size": "medium"},
        )
        assert r.status_code == 200
