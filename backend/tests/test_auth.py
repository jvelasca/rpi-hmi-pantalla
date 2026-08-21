"""Tests del flujo de autenticacion por session-cookie HttpOnly.

Cubre:
- Login (clave correcta/incorrecta) y logout.
- La cookie de sesion se emite con HttpOnly y SameSite=Strict.
- En SECURITY_MODE=protected, los mutadores REST y el WS aceptan la cookie
  (navegador) ademas de X-API-Key (M2M), con loopback exento.
- La cookie malformada/alterada se rechaza.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.app import config as config_module
from backend.app.api.auth import SESSION_COOKIE_NAME, rate_limiter, session_manager
from backend.app.main import app

ADMIN_KEY = "test-key-123"


@pytest.fixture
def protected_mode(monkeypatch):
    """Activa SECURITY_MODE=protected con una ADMIN_API_KEY conocida."""
    monkeypatch.setattr(config_module.settings, "security_mode", "protected")
    monkeypatch.setattr(config_module.settings, "admin_api_key", ADMIN_KEY)
    return ADMIN_KEY


@pytest.fixture(autouse=True)
def clear_sessions():
    """Vacia las sesiones y el rate-limiter en memoria antes de cada test."""
    session_manager.clear()
    rate_limiter.clear()
    yield
    session_manager.clear()
    rate_limiter.clear()


def _login(client: TestClient, api_key: str = ADMIN_KEY) -> str:
    """Realiza login y devuelve el valor de la cookie de sesion."""
    r = client.post("/api/auth/login", json={"api_key": api_key})
    assert r.status_code == 200, r.text
    token = r.cookies.get(SESSION_COOKIE_NAME)
    assert token
    return token


class TestLoginLogout:
    """Comportamiento de POST /api/auth/login y /api/auth/logout."""

    def test_login_sets_httponly_cookie(self, client, protected_mode):
        """Login correcto emite cookie HttpOnly y SameSite=Strict."""
        r = client.post("/api/auth/login", json={"api_key": ADMIN_KEY})
        assert r.status_code == 200
        assert r.json()["authenticated"] is True

        set_cookie = r.headers["set-cookie"].lower()
        assert SESSION_COOKIE_NAME in set_cookie
        assert "httponly" in set_cookie
        assert "samesite=strict" in set_cookie

    def test_login_wrong_key_returns_401(self, client, protected_mode):
        """Login con clave incorrecta -> 401 sin cookie."""
        r = client.post("/api/auth/login", json={"api_key": "wrong-key"})
        assert r.status_code == 401
        assert SESSION_COOKIE_NAME not in r.headers.get("set-cookie", "")

    def test_login_empty_key_returns_401(self, client, protected_mode):
        """Login con clave vacia -> 401."""
        r = client.post("/api/auth/login", json={"api_key": ""})
        assert r.status_code == 401

    def test_logout_revokes_session(self, client, protected_mode):
        """Tras logout la cookie queda invalidada."""
        token = _login(client)
        r = client.post(
            "/api/auth/logout",
            headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"},
        )
        assert r.status_code == 200
        assert r.json()["authenticated"] is False

        # La sesion ya no es valida
        r = client.post(
            "/api/led/on",
            headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"},
        )
        assert r.status_code == 401

    def test_auth_status_reports_mode_and_authenticated(self, client, protected_mode):
        """GET /api/auth/status refleja security_mode y autenticacion."""
        r = client.get("/api/auth/status")
        assert r.status_code == 200
        assert r.json()["security_mode"] == "protected"
        assert r.json()["authenticated"] is False

        _login(client)
        r = client.get("/api/auth/status")
        assert r.json()["authenticated"] is True

    def test_login_unavailable_without_admin_key(self, client):
        """Sin ADMIN_API_KEY configurada, el login devuelve 401."""
        r = client.post("/api/auth/login", json={"api_key": "cualquiera"})
        assert r.status_code == 401


class TestLoginRateLimit:
    """Rate-limiting anti brute-force de POST /api/auth/login."""

    def _fail(self, client: TestClient, n: int) -> None:
        """Realiza ``n`` logins fallidos y verifica que devuelven 401."""
        for _ in range(n):
            r = client.post("/api/auth/login", json={"api_key": "wrong-key"})
            assert r.status_code == 401

    def test_too_many_failures_returns_429(self, client, protected_mode):
        """Superado el limite de fallos, el siguiente intento devuelve 429."""
        max_attempts = rate_limiter.max_attempts
        self._fail(client, max_attempts)
        r = client.post("/api/auth/login", json={"api_key": "wrong-key"})
        assert r.status_code == 429
        assert "detail" in r.json()

    def test_successful_login_resets_counter(self, client, protected_mode):
        """Un login correcto reinicia el contador de fallos de la IP."""
        max_attempts = rate_limiter.max_attempts
        self._fail(client, max_attempts - 1)

        r = client.post("/api/auth/login", json={"api_key": ADMIN_KEY})
        assert r.status_code == 200

        # Tras el reset, una ventana nueva admite max_attempts fallos sin 429.
        self._fail(client, max_attempts)
        r = client.post("/api/auth/login", json={"api_key": "wrong-key"})
        assert r.status_code == 429

    def test_window_expired_allows_retry(self, client, protected_mode, monkeypatch):
        """Al expirar la ventana, la IP vuelve a poder intentar login."""
        max_attempts = rate_limiter.max_attempts
        window_seconds = rate_limiter.window_seconds
        now = [1_000.0]
        monkeypatch.setattr(rate_limiter, "_clock", lambda: now[0])

        self._fail(client, max_attempts)
        r = client.post("/api/auth/login", json={"api_key": "wrong-key"})
        assert r.status_code == 429

        # Avanzar el reloj mas alla de la ventana para poder reintentar.
        now[0] += window_seconds + 1
        r = client.post("/api/auth/login", json={"api_key": "wrong-key"})
        assert r.status_code == 401

    def test_correct_key_not_blocked_after_failures(self, client, protected_mode):
        """El limite no rompe el flujo normal con la clave correcta."""
        max_attempts = rate_limiter.max_attempts
        self._fail(client, max_attempts - 1)
        r = client.post("/api/auth/login", json={"api_key": ADMIN_KEY})
        assert r.status_code == 200
        assert r.json()["authenticated"] is True


class TestRestSessionCookie:
    """Los mutadores REST aceptan la cookie de sesion en protected."""

    def test_mutator_with_cookie_returns_200(self, client, protected_mode):
        """POST /api/led/on con cookie valida (sin X-API-Key) -> 200."""
        token = _login(client)
        r = client.post(
            "/api/led/on",
            headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"},
        )
        assert r.status_code == 200
        assert r.json()["state"] is True

    def test_mutator_without_auth_returns_401(self, client, protected_mode):
        """POST /api/led/on sin cookie ni X-API-Key -> 401."""
        r = client.post("/api/led/on")
        assert r.status_code == 401

    def test_mutator_with_x_api_key_returns_200(self, client, protected_mode):
        """POST /api/led/on con X-API-Key (M2M) sigue funcionando."""
        r = client.post("/api/led/on", headers={"X-API-Key": ADMIN_KEY})
        assert r.status_code == 200

    def test_mutator_with_tampered_cookie_returns_401(self, client, protected_mode):
        """Cookie alterada -> 401."""
        token = _login(client)
        tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
        r = client.post(
            "/api/led/on",
            headers={"Cookie": f"{SESSION_COOKIE_NAME}={tampered}"},
        )
        assert r.status_code == 401

    def test_loopback_still_exempt(self, protected_mode):
        """Desde loopback sigue sin exigir autenticacion."""
        loopback_client = TestClient(app, client=("127.0.0.1", 50000))
        r = loopback_client.post("/api/led/on")
        assert r.status_code == 200


class TestWsSessionCookie:
    """El handshake WebSocket acepta la cookie de sesion en protected."""

    def test_ws_with_cookie_accepted(self, client, protected_mode):
        """WS con cookie valida (sin X-API-Key ni subprotocolo) -> aceptado."""
        token = _login(client)
        with client.websocket_connect(
            "/ws",
            headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"},
        ) as ws:
            ws.send_json({"version": "1.0", "type": "subscribe"})
            data = ws.receive_json()
            assert data["type"] == "status_update"

    def test_ws_without_auth_rejected(self, client, protected_mode):
        """WS sin cookie ni key -> rechazado con 4401."""
        with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect("/ws"):
            pass
        assert exc_info.value.code == 4401

    def test_ws_with_x_api_key_accepted(self, client, protected_mode):
        """WS con X-API-Key (M2M) sigue funcionando."""
        with client.websocket_connect("/ws", headers={"X-API-Key": ADMIN_KEY}) as ws:
            ws.send_json({"version": "1.0", "type": "subscribe"})
            data = ws.receive_json()
            assert data["type"] == "status_update"
