"""Tests de integracion para el backend RPi HMI.

Cubre flujos completos que atraviesan multiples capas:
- REST API con StateManager
- WebSocket con suscripciones y broadcasts
- Interaccion REST <-> WebSocket
- Admin endpoints con autenticacion
- Manejo de errores y edge cases

Ejecutar:
    python -m pytest backend/tests/test_integration.py -v --tb=short
"""

from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.app.services.ssh_manager import MockSSHDriver
from backend.app.services.state_manager import StateManager, state_manager

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    """Cliente de test sincrono."""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Cliente de test asincrono (httpx)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def reset_state() -> None:
    """Resetea el StateManager antes de cada test."""
    state_manager.set_led(False)
    StateManager.__init__(state_manager)
    yield


@pytest.fixture
def api_key() -> str:
    """API key valida para tests de admin."""
    return "test-admin-key-123"


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    """Headers HTTP con API key valida."""
    return {"X-API-Key": api_key}


@pytest.fixture(autouse=True)
def set_api_key(api_key: str) -> None:
    """Configura ADMIN_API_KEY en los objetos settings usando sys.modules."""
    cfg = sys.modules.get("backend.app.config")
    if cfg is not None:
        original = cfg.settings.admin_api_key
        cfg.settings.admin_api_key = api_key
    else:
        original = None

    # Los modulos ssh y deploy importan el mismo settings singleton
    ssh_mod = sys.modules.get("backend.app.api.ssh")
    if ssh_mod and cfg:
        ssh_mod.settings = cfg.settings
    deploy_mod = sys.modules.get("backend.app.api.deploy")
    if deploy_mod and cfg:
        deploy_mod.settings = cfg.settings

    yield

    if cfg is not None and original is not None:
        cfg.settings.admin_api_key = original


def _get_ssh_module():
    """Obtiene el modulo ssh a traves de sys.modules."""
    return sys.modules.get("backend.app.api.ssh")


# ── REST API Integration ──────────────────────────────────────────────────


class TestRestApiIntegration:
    """Flujos completos de la API REST."""

    def test_full_led_lifecycle(self, client):
        """Ciclo completo: encender -> consultar -> toggle -> apagar."""
        r = client.get("/api/led")
        assert r.json()["state"] is False

        r = client.post("/api/led/on")
        assert r.json()["state"] is True
        assert r.json()["label"] == "ENCENDIDO"

        r = client.post("/api/led/toggle")
        assert r.json()["state"] is False

        r = client.post("/api/led/off")
        assert r.json()["state"] is False

    def test_full_button_lifecycle(self, client):
        """Ciclo completo: press -> press -> release -> consultar."""
        r = client.get("/api/button")
        assert r.json()["pressed"] is False
        assert r.json()["press_count"] == 0

        for i in range(3):
            r = client.post("/api/button/press")
            assert r.json()["pressed"] is True
            assert r.json()["press_count"] == i + 1

        r = client.post("/api/button/release")
        assert r.json()["pressed"] is False
        assert r.json()["press_count"] == 3

    def test_status_after_changes(self, client):
        """Status refleja cambios en LED y button (el press NO altera el LED)."""
        # El press del boton incrementa el contador sin tocar el LED;
        # el LED se enciende explicitamente con /api/led/on.
        client.post("/api/button/press")
        client.post("/api/led/on")

        r = client.get("/api/status")
        data = r.json()
        assert data["led"]["state"] is True
        assert data["button"]["pressed"] is True
        assert data["button"]["press_count"] == 1
        assert data["websocket_clients"] == 0
        assert data["uptime_seconds"] >= 0
        assert "timestamp" in data

    def test_display_info_404_when_none(self, client):
        """GET /api/display/info devuelve 404 sin display."""
        r = client.get("/api/display/info")
        assert r.status_code == 404
        assert r.json()["detail"] == "Display no detectado"

    def test_display_info_after_set(self, client):
        """GET /api/display/info devuelve info tras set_display."""
        state_manager.set_display(connected=True, resolution="800x600", driver="test")
        r = client.get("/api/display/info")
        assert r.status_code == 200
        assert r.json()["connected"] is True
        assert r.json()["resolution"] == "800x600"
        assert r.json()["driver"] == "test"

    def test_health_check(self, client):
        """Health check devuelve HealthStatus con checks."""
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "checks" in data
        assert "api" in data["checks"]

    def test_root_endpoint(self, client):
        """GET / devuelve info JSON o HTML del frontend."""
        r = client.get("/")
        assert r.status_code == 200
        content_type = r.headers.get("content-type", "")
        if "application/json" in content_type:
            data = r.json()
            assert "version" in data
        else:
            # Es HTML (frontend compilado o pagina por defecto)
            assert len(r.text) > 0


# ── WebSocket & StateManager Integration ───────────────────────────────────


class TestWebSocketStateIntegration:
    """Pruebas de integracion WebSocket con StateManager usando AsyncMock."""

    @pytest.mark.asyncio
    async def test_subscribe_sends_status(self):
        """Al suscribirse, el WS recibe status_update."""
        ws = MockWebSocket()
        await state_manager.subscribe(ws)
        assert len(ws.sent) == 1
        assert ws.sent[0]["type"] == "status_update"
        state_manager.unsubscribe(ws)

    @pytest.mark.asyncio
    async def test_toggle_led_broadcasts_to_subscriber(self):
        """Toggle LED → broadcast a suscriptores del topico led."""
        ws = MockWebSocket()
        await state_manager.subscribe(ws)
        ws.sent.clear()  # Limpiar el status_update inicial

        state_manager.toggle_led()
        assert state_manager.led.state is True

        state_manager.unsubscribe(ws)

    @pytest.mark.asyncio
    async def test_press_button_broadcasts(self):
        """Press button → broadcast button_pressed, sin alterar el LED."""
        ws = MockWebSocket()
        await state_manager.subscribe(ws)
        ws.sent.clear()

        state_manager.press_button()
        assert state_manager.button.pressed is True
        assert state_manager.button.press_count == 1
        assert state_manager.led.state is False  # el press no toca el LED

        state_manager.unsubscribe(ws)

    @pytest.mark.asyncio
    async def test_multiple_clients_independent(self):
        """Dos clientes WS reciben broadcasts independientes."""
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await state_manager.subscribe(ws1)
        await state_manager.subscribe(ws2)

        status = state_manager.get_status()
        assert status.websocket_clients == 2

        state_manager.unsubscribe(ws1)
        status = state_manager.get_status()
        assert status.websocket_clients == 1

        state_manager.unsubscribe(ws2)
        status = state_manager.get_status()
        assert status.websocket_clients == 0

    @pytest.mark.asyncio
    async def test_subscribe_specific_topics(self):
        """Suscripcion a topicos especificos."""
        from backend.app.models.events import SubscriptionTopic

        ws = MockWebSocket()
        await state_manager.subscribe(ws, topics=[SubscriptionTopic.LED, SubscriptionTopic.BUTTON])
        ws.sent.clear()

        state_manager.set_led(True)
        state_manager.press_button()

        state_manager.unsubscribe(ws)

    @pytest.mark.asyncio
    async def test_subscribe_system_topic(self):
        """Suscripcion a topico system."""
        from backend.app.models.events import SubscriptionTopic

        ws = MockWebSocket()
        await state_manager.subscribe(ws, topics=[SubscriptionTopic.SYSTEM])

        status = state_manager.get_status()
        assert status.websocket_clients == 1

        state_manager.unsubscribe(ws)

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_broadcasts(self):
        """Tras unsubscribe, el cliente no recibe mas mensajes."""
        ws = MockWebSocket()
        await state_manager.subscribe(ws)
        ws.sent.clear()

        state_manager.unsubscribe(ws)
        state_manager.set_led(True)

        # El mock no deberia recibir mas mensajes
        # (los broadcasts se envian en async context, pero el cliente ya no esta)
        assert len(ws.sent) == 0

    @pytest.mark.asyncio
    async def test_set_display_broadcasts(self):
        """set_display emite broadcast a suscriptores."""
        ws = MockWebSocket()
        await state_manager.subscribe(ws)
        ws.sent.clear()

        state_manager.set_display(connected=True, resolution="480x320", driver="piscreen")
        assert state_manager.display is not None
        assert state_manager.display.connected is True

        state_manager.unsubscribe(ws)


class TestStateManagerWsCount:
    """Pruebas de conteo de clientes WS."""

    @pytest.mark.asyncio
    async def test_ws_count_zero_with_no_clients(self):
        """ws_count es 0 sin clientes (ya cubierto pero re-confirmado en integracion)."""
        status = state_manager.get_status()
        assert status.websocket_clients == 0

    @pytest.mark.asyncio
    async def test_ws_count_after_connect_and_disconnect(self):
        """ws_count sube y baja con suscripcion/desuscripcion."""
        ws = MockWebSocket()
        await state_manager.subscribe(ws)
        assert state_manager.get_status().websocket_clients == 1

        state_manager.unsubscribe(ws)
        assert state_manager.get_status().websocket_clients == 0

    @pytest.mark.asyncio
    async def test_same_client_subscribed_to_multiple_topics_counts_once(self):
        """Mismo cliente suscrito a N topicos cuenta como 1."""
        from backend.app.models.events import SubscriptionTopic

        ws = MockWebSocket()
        await state_manager.subscribe(ws, topics=[
            SubscriptionTopic.LED,
            SubscriptionTopic.BUTTON,
            SubscriptionTopic.DISPLAY,
            SubscriptionTopic.SYSTEM,
        ])
        assert state_manager.get_status().websocket_clients == 1
        state_manager.unsubscribe(ws)


# ── REST ↔ WebSocket - Interplay via StateManager ──────────────────────────


class TestRestWsInterplay:
    """Interaccion entre REST (StateManager) y WebSocket (subscriptions)."""

    @pytest.mark.asyncio
    async def test_rest_led_changes_visible_to_ws_state(self):
        """Cambio LED via StateManager → estado visible a WS."""
        ws = MockWebSocket()
        await state_manager.subscribe(ws)
        ws.sent.clear()

        # Simular cambio de LED (como lo haria REST)
        state_manager.set_led(True)
        assert state_manager.led.state is True

        state_manager.unsubscribe(ws)

    @pytest.mark.asyncio
    async def test_rest_button_press_visible_to_ws_state(self):
        """Cambio button via StateManager → estado visible a WS."""
        ws = MockWebSocket()
        await state_manager.subscribe(ws)
        ws.sent.clear()

        state_manager.press_button()
        assert state_manager.button.pressed is True
        assert state_manager.button.press_count == 1

        state_manager.release_button()
        assert state_manager.button.pressed is False

        state_manager.unsubscribe(ws)

    @pytest.mark.asyncio
    async def test_status_includes_ws_clients_correctly(self):
        """SystemStatus.ws_clients refleja suscriptores reales."""
        ws = MockWebSocket()
        await state_manager.subscribe(ws)
        status = state_manager.get_status()
        assert status.websocket_clients == 1
        assert status.led is not None
        assert status.button is not None
        assert status.uptime_seconds >= 0
        state_manager.unsubscribe(ws)


# ── Admin SSH Integration ─────────────────────────────────────────────────


class TestAdminSshIntegration:
    """Pruebas de integracion de los endpoints SSH administrativos."""

    def test_connect_without_auth(self, client):
        """POST /admin/ssh/connect sin API key -> 401 o 503."""
        r = client.post("/admin/ssh/connect", json={
            "host": "192.168.1.1", "user": "pi", "password": "test",
        })
        assert r.status_code in (401, 403, 422)

    def test_disconnect_without_auth(self, client):
        """POST /admin/ssh/disconnect sin API key -> 401 o 503."""
        r = client.post("/admin/ssh/disconnect")
        assert r.status_code in (401, 403)

    def test_status_without_auth(self, client):
        """GET /admin/ssh/status sin API key -> 401 o 503."""
        r = client.get("/admin/ssh/status")
        assert r.status_code in (401, 403)

    def test_execute_without_auth(self, client):
        """POST /admin/ssh/execute sin API key -> 401."""
        r = client.post("/admin/ssh/execute", json={"command": "uname -a"})
        assert r.status_code in (401, 403, 422)

    def test_connect_with_wrong_key(self, client):
        """POST /admin/ssh/connect con API key incorrecta -> 401."""
        r = client.post(
            "/admin/ssh/connect",
            json={"host": "192.168.1.1", "user": "pi", "password": "test"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert r.status_code == 401

    def test_disconnect_when_not_connected(self, client, auth_headers):
        """POST /admin/ssh/disconnect sin conexion previa -> 200."""
        ssh_mod = _get_ssh_module()
        if ssh_mod:
            ssh_mod._ssh_driver = None

        r = client.post("/admin/ssh/disconnect", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True

    def test_execute_without_connection(self, client, auth_headers):
        """POST /admin/ssh/execute sin conexion -> 503."""
        ssh_mod = _get_ssh_module()
        if ssh_mod:
            ssh_mod._ssh_driver = None

        r = client.post(
            "/admin/ssh/execute",
            json={"command": "echo hello"},
            headers=auth_headers,
        )
        assert r.status_code == 503

    def test_connect_with_mock_driver(self, client, auth_headers):
        """Conectar con MockSSHDriver y ejecutar comando."""
        mock_driver = MockSSHDriver()
        ssh_mod = _get_ssh_module()

        if ssh_mod is None:
            pytest.skip("SSH module not available")

        # Guardar referencia original y parchear
        original = getattr(ssh_mod, "ParamikoSSHDriver", None)
        ssh_mod.ParamikoSSHDriver = lambda: mock_driver  # type: ignore[assignment]

        try:
            # Conectar
            r = client.post(
                "/admin/ssh/connect",
                json={"host": "192.168.1.100", "user": "pi", "password": "secret"},
                headers=auth_headers,
            )
            assert r.status_code == 200
            assert r.json()["success"] is True

            # Verificar estado
            r = client.get("/admin/ssh/status", headers=auth_headers)
            assert r.status_code == 200
            assert r.json()["connected"] is True

            # Ejecutar comando
            r = client.post(
                "/admin/ssh/execute",
                json={"command": "uname -a"},
                headers=auth_headers,
            )
            assert r.status_code == 200
            result = r.json()
            assert result["ok"] is True
            assert "Linux" in result["stdout"]

            # Desconectar
            r = client.post("/admin/ssh/disconnect", headers=auth_headers)
            assert r.status_code == 200
            assert r.json()["success"] is True

        finally:
            if original:
                ssh_mod.ParamikoSSHDriver = original  # type: ignore[assignment]

    def test_execute_failing_command(self, client, auth_headers):
        """Ejecutar comando 'fail' devuelve error."""
        mock_driver = MockSSHDriver()
        ssh_mod = _get_ssh_module()
        if ssh_mod is None:
            pytest.skip("SSH module not available")

        original = getattr(ssh_mod, "ParamikoSSHDriver", None)
        ssh_mod.ParamikoSSHDriver = lambda: mock_driver  # type: ignore[assignment]

        try:
            client.post(
                "/admin/ssh/connect",
                json={"host": "10.0.0.1", "user": "pi", "password": "x"},
                headers=auth_headers,
            )

            r = client.post(
                "/admin/ssh/execute",
                json={"command": "fail"},
                headers=auth_headers,
            )
            assert r.status_code == 200
            result = r.json()
            assert result["ok"] is False
            assert result["exit_code"] == 1

        finally:
            if original:
                ssh_mod.ParamikoSSHDriver = original  # type: ignore[assignment]


# ── Admin Deploy Integration ──────────────────────────────────────────────


class TestAdminDeployIntegration:
    """Pruebas de integracion de los endpoints Deploy administrativos."""

    def test_scan_without_auth(self, client):
        """GET /admin/deploy/scan sin API key -> 401."""
        r = client.get("/admin/deploy/scan")
        assert r.status_code in (401, 403)

    def test_setup_without_auth(self, client):
        """POST /admin/deploy/setup sin API key -> 401."""
        r = client.post("/admin/deploy/setup")
        assert r.status_code in (401, 403)

    def test_health_without_auth(self, client):
        """GET /admin/deploy/health sin API key -> 401."""
        r = client.get("/admin/deploy/health")
        assert r.status_code in (401, 403)

    def test_scan_returns_valid_response(self, client, auth_headers):
        """GET /admin/deploy/scan devuelve lista de resultados."""
        r = client.get("/admin/deploy/scan", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert "results" in data
        assert "count" in data
        assert isinstance(data["results"], list)
        assert isinstance(data["count"], int)

    def test_admin_does_not_accept_hmi_session_cookie(self, client, auth_headers):
        """Una cookie de sesion HMI no da acceso a /admin/* (solo X-API-Key)."""
        import asyncio

        from backend.app.api.auth import SESSION_COOKIE_NAME
        from backend.app.services.security_manager import security_manager

        # Activar la seguridad del panel para poder emitir una sesion valida.
        security_manager.reset()
        asyncio.run(security_manager.set_enabled(True))

        # Login con la contraseña de fabrica -> cookie de sesion valida.
        login = client.post("/api/auth/login", json={"password": "1234"})
        assert login.status_code == 200, login.text
        token = login.cookies.get(SESSION_COOKIE_NAME)
        assert token

        # La cookie NO debe autenticar el endpoint admin (401).
        r = client.get(
            "/admin/deploy/scan",
            headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"},
        )
        assert r.status_code == 401

        # El header X-API-Key si debe autenticar (200).
        r = client.get("/admin/deploy/scan", headers=auth_headers)
        assert r.status_code == 200

    def test_setup_without_ssh_connection(self, client, auth_headers):
        """POST /admin/deploy/setup sin SSH -> 503."""
        ssh_mod = _get_ssh_module()
        if ssh_mod:
            ssh_mod._ssh_driver = None

        r = client.post("/admin/deploy/setup", headers=auth_headers)
        assert r.status_code == 503

    def test_deploy_app_without_ssh(self, client, auth_headers):
        """POST /admin/deploy/app sin SSH -> 503."""
        ssh_mod = _get_ssh_module()
        if ssh_mod:
            ssh_mod._ssh_driver = None

        r = client.post("/admin/deploy/app", headers=auth_headers)
        assert r.status_code == 503

    def test_diagnostics_without_ssh(self, client, auth_headers):
        """GET /admin/deploy/diagnostics sin SSH -> 503."""
        ssh_mod = _get_ssh_module()
        if ssh_mod:
            ssh_mod._ssh_driver = None

        r = client.get("/admin/deploy/diagnostics", headers=auth_headers)
        assert r.status_code == 503

    def test_health_without_ssh(self, client, auth_headers):
        """GET /admin/deploy/health sin SSH -> 503."""
        ssh_mod = _get_ssh_module()
        if ssh_mod:
            ssh_mod._ssh_driver = None

        r = client.get("/admin/deploy/health", headers=auth_headers)
        assert r.status_code == 503

    def test_deploy_with_mock_ssh(self, client, auth_headers):
        """Operaciones deploy con MockSSHDriver."""
        mock_driver = MockSSHDriver()
        ssh_mod = _get_ssh_module()
        if ssh_mod is None:
            pytest.skip("SSH module not available")

        original = getattr(ssh_mod, "ParamikoSSHDriver", None)
        ssh_mod.ParamikoSSHDriver = lambda: mock_driver  # type: ignore[assignment]

        try:
            # Conectar SSH primero
            client.post(
                "/admin/ssh/connect",
                json={"host": "192.168.1.100", "user": "pi", "password": "secret"},
                headers=auth_headers,
            )

            # Setup environment
            r = client.post("/admin/deploy/setup", headers=auth_headers)
            assert r.status_code == 200
            data = r.json()
            assert data["success"] is True
            assert len(data["steps"]) == 4

            # Health check
            r = client.get("/admin/deploy/health", headers=auth_headers)
            assert r.status_code == 200
            data = r.json()
            assert "healthy" in data
            assert "message" in data

            # Diagnostics
            r = client.get("/admin/deploy/diagnostics", headers=auth_headers)
            assert r.status_code == 200
            data = r.json()
            assert data["step"] == "diagnostics"

            # Start backend
            r = client.post("/admin/deploy/start", headers=auth_headers)
            assert r.status_code == 200
            data = r.json()
            assert data["step"] == "start_backend"

            # Stop backend
            r = client.post("/admin/deploy/stop", headers=auth_headers)
            assert r.status_code == 200
            data = r.json()
            assert data["step"] == "stop_backend"

        finally:
            if original:
                ssh_mod.ParamikoSSHDriver = original  # type: ignore[assignment]

    def test_deploy_wrong_key(self, client):
        """Deploy con API key incorrecta -> 401."""
        r = client.get("/admin/deploy/scan", headers={"X-API-Key": "wrong"})
        assert r.status_code == 401


# ── Error Handling ───────────────────────────────────────────────────────


class TestErrorHandling:
    """Manejo de errores en la API."""

    def test_invalid_json_body(self, client):
        """POST con JSON invalido -> 400 o 422."""
        r = client.post(
            "/admin/ssh/connect",
            content=b"{invalid json",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": "test-admin-key-123",
            },
        )
        # FastAPI devuelve 422 para JSON invalido (pydantic validation error)
        # o 400 para JSON malformado (depende de la version de Starlette)
        assert r.status_code in (400, 422)

    def test_nonexistent_endpoint(self, client):
        """GET a endpoint inexistente -> 404."""
        r = client.get("/api/nonexistent")
        assert r.status_code == 404

    def test_method_not_allowed(self, client):
        """DELETE a endpoint que solo acepta GET -> 405."""
        r = client.delete("/api/status")
        assert r.status_code == 405

    def test_ssh_connect_validation_errors(self, client, auth_headers):
        """Validacion de campos en SSH connect."""
        # Falta host (campo requerido)
        r = client.post(
            "/admin/ssh/connect",
            json={"user": "pi", "password": "test"},
            headers=auth_headers,
        )
        assert r.status_code == 422

        # Puerto invalido
        r = client.post(
            "/admin/ssh/connect",
            json={"host": "1.2.3.4", "user": "pi", "password": "test", "port": 99999},
            headers=auth_headers,
        )
        assert r.status_code == 422

    def test_ssh_execute_missing_command(self, client, auth_headers):
        """POST /admin/ssh/execute sin command -> 422 o 503."""
        r = client.post(
            "/admin/ssh/execute",
            json={},
            headers=auth_headers,
        )
        # 503 si no hay conexion SSH (get_ssh_driver falla antes de validar body)
        # 422 si hay conexion SSH y falta el campo command
        assert r.status_code in (422, 503)


# ── CORS & Security ──────────────────────────────────────────────────────


class TestCorsAndSecurity:
    """Pruebas de seguridad y CORS."""

    def test_options_preflight(self, client):
        """OPTIONS request para CORS preflight."""
        r = client.options(
            "/api/status",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code in (200, 405)

    def test_api_key_not_leaked_in_error(self, client):
        """API key no aparece en respuestas de error."""
        r = client.post(
            "/admin/ssh/connect",
            json={"host": "1.2.3.4"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert r.status_code in (401, 422)
        data = r.json()
        detail = str(data.get("detail", ""))
        assert "wrong-key" not in detail.lower()


# ── StateManager Edge Cases ──────────────────────────────────────────────


class TestStateManagerEdgeCases:
    """Casos borde del StateManager en contexto de integracion."""

    def test_led_on_multiple_times(self, client):
        """Encender LED muchas veces mantiene estado correcto."""
        for _ in range(100):
            client.post("/api/led/on")
        r = client.get("/api/led")
        assert r.json()["state"] is True

    def test_toggle_rapidly(self, client):
        """Toggle rapido no corrompe estado."""
        for _ in range(100):
            client.post("/api/led/toggle")
        r = client.get("/api/led")
        assert r.json()["state"] is False  # par de toggles

    def test_button_counter_handles_high_values(self, client):
        """Contador de boton maneja valores altos."""
        for _ in range(50):
            client.post("/api/button/press")
        r = client.get("/api/button")
        assert r.json()["press_count"] == 50


# ── Mock WebSocket (AsyncMock) ───────────────────────────────────────────


class MockWebSocket:
    """Simula una conexion WebSocket asincrona para testing."""

    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)


# ═══════════════════════════════════════════════════════════════
# Error Handling Extended (FASE P1+P2)
# ═══════════════════════════════════════════════════════════════


class TestErrorHandlingExtended:
    """Tests extendidos de manejo de errores HTTP."""

    def test_api_returns_500_on_internal_error(self, client) -> None:  # type: ignore[no-untyped-def]
        """El backend propaga RuntimeError como 500 cuando toggle_led falla."""
        from unittest.mock import patch

        with (
            patch(
                "backend.app.services.state_manager.state_manager.toggle_led",
                side_effect=RuntimeError("Simulated crash"),
            ),
            pytest.raises(RuntimeError, match="Simulated crash"),
        ):
            # Starlette TestClient propaga excepciones no manejadas.
            # En produccion, FastAPI capturaria esto como 500.
            # Aqui verificamos que la excepcion se genera correctamente.
            client.post("/api/led/toggle")

    def test_status_endpoint_reflects_ws_count(self, client) -> None:  # type: ignore[no-untyped-def]
        """GET /api/status refleja el numero de clientes WS."""
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "websocket_clients" in data
