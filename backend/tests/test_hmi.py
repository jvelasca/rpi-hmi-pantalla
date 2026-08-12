"""Tests para los endpoints HMI REST.

Valida:
- Todos los endpoints devuelven codigos HTTP correctos
- Los modelos de respuesta son validos
- Las operaciones de toggle son idempotentes
- POST /api/led/on y /api/led/off mutan el estado correctamente
- GET /api/status incluye todos los subsistemas
"""

from __future__ import annotations

import pytest

from backend.app.main import app
from backend.app.services.state_manager import StateManager


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
