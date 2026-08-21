"""Tests de la gestión de contraseña del panel web (FASE 6).

Cubre:
- Login con la contraseña de fábrica ``1234`` cuando la seguridad está activada.
- ``GET /api/auth/security`` refleja ``enabled``/``is_default``.
- Cambio de contraseña: la vieja deja de funcionar, la nueva funciona y las
  sesiones se revocan.
- Activar/desactivar se refleja en ``/api/auth/status`` y en la dependencia
  ``require_admin_api_key``.
- Los endpoints de seguridad exigen autorización (401 sin credenciales).
- Round-trip de persistencia (guardar/cargar) y migración 003.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from backend.app import config as config_module
from backend.app.api.auth import SESSION_COOKIE_NAME, rate_limiter, session_manager
from backend.app.services.password_hash import (
    DEFAULT_PASSWORD,
    hash_password,
    verify_password,
)
from backend.app.services.persistence import Persistence
from backend.app.services.security_manager import SecurityManager, security_manager

ADMIN_KEY = "test-key-123"


@pytest.fixture
def protected_mode(monkeypatch):
    """Activa la seguridad del panel con una ADMIN_API_KEY conocida."""
    monkeypatch.setattr(config_module.settings, "security_mode", "protected")
    monkeypatch.setattr(config_module.settings, "admin_api_key", ADMIN_KEY)
    security_manager.reset()  # enabled=False + contraseña "1234"
    asyncio.run(security_manager.set_enabled(True))
    return ADMIN_KEY


@pytest.fixture(autouse=True)
def clear_runtime():
    """Vacia sesiones y rate-limiter antes de cada test."""
    session_manager.clear()
    rate_limiter.clear()
    yield
    session_manager.clear()
    rate_limiter.clear()


def _login(client: TestClient, password: str = DEFAULT_PASSWORD) -> str:
    """Realiza login y devuelve el token de cookie de sesión."""
    r = client.post("/api/auth/login", json={"password": password})
    assert r.status_code == 200, r.text
    return r.cookies.get(SESSION_COOKIE_NAME)


class TestSecurityStatus:
    """Comportamiento de GET /api/auth/security y login con contraseña."""

    def test_security_status_reflects_default(self, client, protected_mode):
        """Con la seguridad activada, GET /auth/security refleja enabled y default."""
        r = client.get("/api/auth/security")
        assert r.status_code == 200
        assert r.json() == {"enabled": True, "is_default": True}

    def test_security_status_disabled_by_default(self, client):
        """Sin activar, GET /auth/security refleja enabled=False."""
        r = client.get("/api/auth/security")
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    def test_security_manager_disabled_after_reset(self):
        """El estado por defecto del SecurityManager es desactivado."""
        security_manager.reset()
        assert security_manager.is_enabled() is False

    def test_login_with_default_password(self, client, protected_mode):
        """El login con la contraseña de fábrica funciona con la seguridad activada."""
        r = client.post("/api/auth/login", json={"password": DEFAULT_PASSWORD})
        assert r.status_code == 200
        assert r.json()["authenticated"] is True

    def test_login_with_wrong_password_fails(self, client, protected_mode):
        """Un login con contraseña incorrecta devuelve 401."""
        r = client.post("/api/auth/login", json={"password": "incorrecta"})
        assert r.status_code == 401


class TestSecurityEndpointsAuthorization:
    """Los endpoints de cambio de seguridad exigen autorización."""

    def test_toggle_without_credentials_returns_401(self, client, protected_mode):
        """POST /auth/security sin credenciales -> 401."""
        r = client.post("/api/auth/security", json={"enabled": False})
        assert r.status_code == 401

    def test_toggle_with_x_api_key_authorized(self, client, protected_mode):
        """POST /auth/security con X-API-Key -> autorizado."""
        r = client.post(
            "/api/auth/security",
            json={"enabled": False},
            headers={"X-API-Key": ADMIN_KEY},
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is False

    def test_toggle_with_current_authorized(self, client, protected_mode):
        """POST /auth/security con `current` correcto -> autorizado."""
        r = client.post(
            "/api/auth/security",
            json={"enabled": False, "current": DEFAULT_PASSWORD},
        )
        assert r.status_code == 200

    def test_toggle_with_session_cookie_authorized(self, client, protected_mode):
        """POST /auth/security con cookie de sesión -> autorizado."""
        token = _login(client)
        r = client.post(
            "/api/auth/security",
            json={"enabled": False},
            headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"},
        )
        assert r.status_code == 200

    def test_change_password_with_wrong_current_returns_401(self, client, protected_mode):
        """POST /auth/password con `current` incorrecto -> 401."""
        r = client.post(
            "/api/auth/password",
            json={"current": "incorrecta", "new": "56781234"},
        )
        assert r.status_code == 401

    def test_change_password_short_new_returns_422(self, client, protected_mode):
        """POST /auth/password con `new` de menos de 8 caracteres -> 422."""
        r = client.post(
            "/api/auth/password",
            json={"current": DEFAULT_PASSWORD, "new": "1234567"},
        )
        assert r.status_code == 422


class TestToggleEnabled:
    """Activar/desactivar cambia el comportamiento de auth."""

    def test_enable_requires_auth_for_mutators(self, client):
        """Al activar (tras cambiar la de fábrica), auth/status pasa a protected
        y los mutadores exigen auth."""
        # Primero se cambia la contraseña de fábrica (mín. 8).
        r = client.post(
            "/api/auth/password",
            json={"current": DEFAULT_PASSWORD, "new": "nueva-clave-123"},
        )
        assert r.status_code == 200

        r = client.post(
            "/api/auth/security",
            json={"enabled": True, "current": "nueva-clave-123"},
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is True

        status = client.get("/api/auth/status").json()
        assert status["security_mode"] == "protected"
        assert status["authenticated"] is False

        # Mutador sin auth -> 401
        assert client.post("/api/led/on").status_code == 401

    def test_enable_with_default_password_returns_409(self, client):
        """Activar la protección con la contraseña de fábrica devuelve 409."""
        r = client.post(
            "/api/auth/security",
            json={"enabled": True, "current": DEFAULT_PASSWORD},
        )
        assert r.status_code == 409
        assert "1234" in r.json()["detail"]

    def test_disable_restores_local_mode(self, client, protected_mode):
        """Al desactivar, auth/status vuelve a local y los mutadores no exigen auth."""
        r = client.post(
            "/api/auth/security",
            json={"enabled": False, "current": DEFAULT_PASSWORD},
        )
        assert r.status_code == 200
        assert r.json()["enabled"] is False

        status = client.get("/api/auth/status").json()
        assert status["security_mode"] == "local"
        assert status["authenticated"] is True

        # Mutador sin auth -> 200
        assert client.post("/api/led/on").status_code == 200


class TestChangePassword:
    """Cambio de contraseña: la vieja falla, la nueva funciona y revoca sesiones."""

    def test_change_password_revokes_sessions_and_rotates(self, client, protected_mode):
        """Cambiar contraseña invalida la vieja, habilita la nueva y revoca sesiones."""
        token = _login(client)

        r = client.post(
            "/api/auth/password",
            json={"current": DEFAULT_PASSWORD, "new": "nueva-clave-123"},
        )
        assert r.status_code == 200
        assert r.json() == {"success": True}

        # La contraseña vieja ya no funciona
        assert client.post(
            "/api/auth/login", json={"password": DEFAULT_PASSWORD}
        ).status_code == 401

        # La nueva funciona
        assert client.post(
            "/api/auth/login", json={"password": "nueva-clave-123"}
        ).status_code == 200

        # La sesión emitida antes del cambio quedó revocada
        r = client.post(
            "/api/led/on",
            headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"},
        )
        assert r.status_code == 401

    def test_is_default_after_change_is_false(self, client, protected_mode):
        """Tras cambiar la contraseña, is_default pasa a False."""
        client.post(
            "/api/auth/password",
            json={"current": DEFAULT_PASSWORD, "new": "nueva-clave-123"},
        )
        r = client.get("/api/auth/security")
        assert r.json()["is_default"] is False


class TestPersistenceRoundTrip:
    """Round-trip de persistencia y migración 003."""

    @pytest.mark.asyncio
    async def test_migration_003_seeds_default_row(self):
        """La migración 003 crea la fila con hash de ``1234`` y flag desactivado."""
        db = Persistence(":memory:")
        await db.init()
        try:
            data = await db.get_security_settings()
            # La migración 003 siembra siempre password_enabled=0 (off por defecto).
            assert data["password_enabled"] is False
            assert verify_password(DEFAULT_PASSWORD, str(data["password_hash"]))
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_save_and_load_round_trip(self):
        """Guardar y cargar la configuración de seguridad es consistente."""
        db = Persistence(":memory:")
        await db.init()
        try:
            await db.save_security_settings(hash_password("abcd"), True)
            data = await db.get_security_settings()
            assert data["password_enabled"] is True
            assert verify_password("abcd", str(data["password_hash"]))

            sm = SecurityManager()
            await sm.load(db)
            assert sm.is_enabled() is True
            assert sm.verify_password("abcd") is True
            assert sm.verify_password(DEFAULT_PASSWORD) is False

            await sm.set_password("9999")
            assert sm.verify_password("9999") is True
            reloaded = await db.get_security_settings()
            assert verify_password("9999", str(reloaded["password_hash"]))
        finally:
            await db.close()
