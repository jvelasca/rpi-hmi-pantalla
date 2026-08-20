"""Tests para la capa de persistencia SQLite y el health check.

Cubre:
- Persistence: init, save_led, get_led, save_button_count, get_button_count, log_event, is_healthy
- Health endpoint: respuesta con checks individuales
"""

import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from backend.app.services.persistence import Persistence

# ── Persistence Tests ──────────────────────────────────────────

class TestPersistence:
    """Tests de la capa de persistencia SQLite."""

    @pytest_asyncio.fixture
    async def db(self):
        """Crea una BD temporal para cada test."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        p = Persistence(path)
        await p.init()
        yield p
        await p.close()
        Path(path).unlink(missing_ok=True)

    async def test_init_creates_db(self, db):
        """La BD se crea y es healthy tras init."""
        assert db is not None
        healthy = await db.is_healthy()
        assert healthy is True

    async def test_save_and_get_led(self, db):
        """Guarda y recupera el estado del LED."""
        await db.save_led(state=True)
        state = await db.get_led()
        assert state is True

        await db.save_led(state=False)
        state = await db.get_led()
        assert state is False

    async def test_get_led_defaults_on_first_run(self, db):
        """Antes de guardar, get_led devuelve False."""
        state = await db.get_led()
        assert state is False

    async def test_save_and_get_button_count(self, db):
        """Guarda y recupera el contador de pulsaciones."""
        await db.save_button_count(5)
        count = await db.get_button_count()
        assert count == 5

        await db.save_button_count(100)
        count = await db.get_button_count()
        assert count == 100

    async def test_get_button_count_defaults_on_first_run(self, db):
        """Antes de guardar, get_button_count devuelve 0."""
        count = await db.get_button_count()
        assert count == 0

    async def test_log_event(self, db):
        """Registra eventos en el log."""
        await db.log_event("led_on", '{"state": true}')
        await db.log_event("button_pressed", '{"count": 1}')

        events = await db.get_recent_events(limit=10)
        assert len(events) == 2
        # Mas reciente primero
        assert events[0]["event_type"] == "button_pressed"
        assert events[1]["event_type"] == "led_on"

    async def test_get_recent_events_limit(self, db):
        """Respeta el limite de eventos."""
        for i in range(20):
            await db.log_event("test", f'{{"num": {i}}}')
        events = await db.get_recent_events(limit=5)
        assert len(events) == 5

    async def test_is_healthy_closed_db(self):
        """Una BD cerrada NO es healthy."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        p = Persistence(path)
        await p.init()
        assert await p.is_healthy() is True
        await p.close()
        assert await p.is_healthy() is False
        Path(path).unlink(missing_ok=True)


# ── Health Endpoint Tests (HTTP) ───────────────────────────────

class TestHealthEndpoint:
    """Tests del endpoint /health via TestClient."""

    def test_health_status_200(self, client):
        """GET /health devuelve 200."""
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_has_required_fields(self, client):
        """HealthStatus tiene campos obligatorios."""
        r = client.get("/health")
        data = r.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "checks" in data
        assert "timestamp" in data
        assert "uptime_seconds" in data

    def test_health_checks_all_subsystems(self, client):
        """Todos los subsistemas tienen check."""
        r = client.get("/health")
        checks = r.json()["checks"]
        expected = {"api", "uptime", "gpio", "display", "db", "cpu", "ws"}
        assert set(checks.keys()) == expected

    def test_health_each_check_has_status_message(self, client):
        """Cada check tiene status y message."""
        r = client.get("/health")
        for name, check in r.json()["checks"].items():
            assert check["status"] in ("pass", "warn", "fail"), f"{name}: status={check['status']}"
            assert isinstance(check["message"], str), f"{name}: message no es string"

    def test_health_live_returns_200(self, client):
        """GET /health/live siempre devuelve 200."""
        r = client.get("/health/live")
        assert r.status_code == 200

    def test_health_ready_accessible(self, client):
        """GET /health/ready es accesible."""
        r = client.get("/health/ready")
        assert r.status_code in (200, 503)


# ── Persistence Edge Cases ─────────────────────────────────────


class TestPersistenceEdgeCases:
    """Casos limite de la capa de persistencia."""

    @pytest.mark.asyncio
    async def test_get_persistence_singleton_reuses_instance(self):
        """Llamar get_persistence dos veces devuelve la misma instancia."""
        from backend.app.services.persistence import close_persistence, get_persistence

        await close_persistence()  # Reset singleton
        db1 = await get_persistence(":memory:")
        db2 = await get_persistence(":memory:")
        assert db1 is db2
        await close_persistence()

    @pytest.mark.asyncio
    async def test_close_persistence_and_reinit(self):
        """Cerrar y reabrir la BD funciona."""
        from backend.app.services.persistence import close_persistence, get_persistence

        await close_persistence()
        db = await get_persistence(":memory:")
        await db.save_led(True)
        assert await db.get_led() is True
        await close_persistence()
        # Reopen — in-memory starts fresh
        db2 = await get_persistence(":memory:")
        assert await db2.get_led() is False
        await close_persistence()

    @pytest.mark.asyncio
    async def test_event_log_rotation_deletes_old_rows(self):
        """Al insertar mas de MAX_EVENT_LOG_ROWS eventos, los viejos se eliminan."""
        from backend.app.services.persistence import Persistence

        db = Persistence(":memory:")
        await db.init()
        max_rows = db.MAX_EVENT_LOG_ROWS
        # Insert MAX + 500 events
        for i in range(max_rows + 500):
            await db.log_event(f"test_{i}")
        # Count remaining
        cursor = await db._conn.execute("SELECT COUNT(*) FROM event_log")
        row = await cursor.fetchone()
        count = row[0]
        assert count <= max_rows  # Should have rotated down
        await db.close()

    @pytest.mark.asyncio
    async def test_save_led_with_closed_connection_returns_silently(self):
        """Guardar LED con BD cerrada no crashea."""
        from backend.app.services.persistence import Persistence

        db = Persistence(":memory:")
        await db.init()
        await db.close()
        await db.save_led(True)  # Should return silently (checks self._conn)

    @pytest.mark.asyncio
    async def test_concurrent_writes_dont_corrupt(self):
        """Escrituras concurrentes no corrompen la BD."""
        import asyncio

        from backend.app.services.persistence import Persistence

        db = Persistence(":memory:")
        await db.init()

        async def write_loop():
            for i in range(10):
                await db.save_led(True)
                await db.save_button_count(i)
                await db.log_event("concurrent", f'{{"i": {i}}}')

        tasks = [asyncio.create_task(write_loop()) for _ in range(5)]
        await asyncio.gather(*tasks)
        # Verify data integrity
        led = await db.get_led()
        count = await db.get_button_count()
        assert isinstance(led, bool)
        assert isinstance(count, int)
        await db.close()
