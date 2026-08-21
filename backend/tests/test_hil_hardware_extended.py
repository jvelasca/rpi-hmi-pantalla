"""Tests HIL (Hardware-In-the-Loop) ampliados para los escenarios pendientes
del cierre de Fase 8:

- login/logout del panel web (sesión por cookie HttpOnly).
- SQLite fail-closed ante una BD persistida ausente/corrupta.
- integridad de arranque (proxy de "apagado brusco"): unidades systemd
  active/running, watchdog sin reinicios y journal sin bucle de arranque.

Misma política de doble skip que ``test_hil_hardware.py``: a nivel de módulo
salvo ``RPI_HIL=1``, y por recurso/endpoint ausente en cada test, para no
fallar nunca en Windows/CI. Los tests de red usan solo stdlib (urllib +
http.cookiejar); los de systemd/journal usan subprocess y se saltan si las
herramientas no existen.
"""

from __future__ import annotations

import contextlib
import http.cookiejar
import json
import os
import sqlite3
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import pytest

HARDWARE_AVAILABLE = os.environ.get("RPI_HIL") == "1"

pytestmark = [
    pytest.mark.hardware,
    pytest.mark.skipif(
        not HARDWARE_AVAILABLE,
        reason="HIL: requiere Raspberry Pi fisica (RPI_HIL=1)",
    ),
]

_BACKEND_BASE_URL = "http://localhost:8000"

# Nombre de la cookie de sesión y contraseña por defecto del panel web
# (definidos en backend/app/api/auth.py y backend/app/services/password_hash.py).
_SESSION_COOKIE_NAME = "rpi_hmi_session"
_DEFAULT_PASSWORD = "1234"

# Unidades systemd instaladas por el despliegue (config/systemd/).
_BACKEND_SERVICE = "rpi-hmi-backend.service"
_DISPLAY_SERVICE = "rpi-hmi-display.service"


def _build_opener() -> tuple[http.cookiejar.CookieJar, urllib.request.OpenerDirector]:
    """Crea un opener con CookieJar para gestionar la cookie de sesión."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    return jar, opener


def _cookie_value(jar: http.cookiejar.CookieJar, name: str) -> str | None:
    """Devuelve el valor de la cookie ``name`` almacenada en el jar (o None)."""
    for cookie in jar:
        if cookie.name == name:
            return cookie.value or None
    return None


def _run_command(
    args: list[str], timeout: float = 15.0
) -> subprocess.CompletedProcess[str] | None:
    """Ejecuta ``args`` con salida capturada.

    Returns:
        ``CompletedProcess`` con stdout/stderr, o ``None`` si el comando no
        existe, no puede ejecutarse o excede el timeout (recurso ausente).
    """
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None


# ── Login / logout del panel web ───────────────────────────────


@pytest.mark.hardware
def test_auth_login_logout_session() -> None:
    """Login/logout del panel web: cookie de sesión emitida y luego revocada."""
    jar, opener = _build_opener()
    login_url = f"{_BACKEND_BASE_URL}/api/auth/login"
    logout_url = f"{_BACKEND_BASE_URL}/api/auth/logout"
    status_url = f"{_BACKEND_BASE_URL}/api/auth/status"

    # 1. Login con la contraseña por defecto (1234).
    login_req = urllib.request.Request(
        login_url,
        data=json.dumps({"password": _DEFAULT_PASSWORD}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener.open(login_req, timeout=60.0) as response:
            assert response.status == 200
            login_data = json.load(response)
            assert login_data.get("authenticated") is True
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            pytest.skip(
                "La contraseña del panel no es la de fábrica (1234); login no verificable"
            )
        if exc.code == 429:
            pytest.skip("Login bloqueado por rate-limit; reintenta más tarde")
        pytest.fail(f"Login respondió HTTP {exc.code}")
    except (urllib.error.URLError, OSError) as exc:
        pytest.skip(f"Backend no accesible en {login_url}: {exc}")

    token = _cookie_value(jar, _SESSION_COOKIE_NAME)
    if not token:
        pytest.fail("Login no emitió la cookie de sesión rpi_hmi_session")

    # 2. Una petición autenticada con la cookie funciona.
    try:
        with opener.open(status_url, timeout=5.0) as response:
            assert response.status == 200
            status_data = json.load(response)
            assert status_data.get("authenticated") is True
            security_enabled = bool(status_data.get("security_enabled"))
    except urllib.error.HTTPError as exc:
        pytest.fail(f"GET /api/auth/status respondió HTTP {exc.code}")
    except (urllib.error.URLError, OSError) as exc:
        pytest.skip(f"Backend no accesible en {status_url}: {exc}")

    # 3. Logout.
    logout_req = urllib.request.Request(logout_url, data=b"", method="POST")
    try:
        with opener.open(logout_req, timeout=5.0) as response:
            assert response.status == 200
            logout_data = json.load(response)
            assert logout_data.get("authenticated") is False
            logout_set_cookie = response.headers.get("Set-Cookie", "")
    except urllib.error.HTTPError as exc:
        pytest.fail(f"Logout respondió HTTP {exc.code}")
    except (urllib.error.URLError, OSError) as exc:
        pytest.skip(f"Backend no accesible en {logout_url}: {exc}")

    # 4. La cookie queda invalidada: logout debe borrarla (Max-Age=0) y el
    #    jar ya no debe contenerla.
    if _SESSION_COOKIE_NAME not in logout_set_cookie or "Max-Age=0" not in logout_set_cookie:
        pytest.fail(f"Logout no borró la cookie de sesión (Set-Cookie={logout_set_cookie!r})")
    if _cookie_value(jar, _SESSION_COOKIE_NAME) is not None:
        pytest.fail("La cookie de sesión sigue presente en el jar tras logout")

    # 5. Revocación server-side: con la seguridad del panel activada, el token
    #    antiguo debe dejar de autenticar. Con la seguridad desactivada el
    #    endpoint /api/auth/status siempre reporta authenticated=true, por lo
    #    que este chequeo extra solo es significativo en modo protegido.
    if security_enabled:
        old_token_req = urllib.request.Request(
            status_url,
            headers={"Cookie": f"{_SESSION_COOKIE_NAME}={token}"},
        )
        try:
            with urllib.request.urlopen(old_token_req, timeout=5.0) as response:
                after_logout = json.load(response)
                assert after_logout.get("authenticated") is False
        except urllib.error.HTTPError as exc:
            pytest.fail(f"GET /api/auth/status (post-logout) respondió HTTP {exc.code}")
        except (urllib.error.URLError, OSError) as exc:
            pytest.skip(f"Backend no accesible en {status_url}: {exc}")


# ── SQLite fail-closed ─────────────────────────────────────────


@pytest.mark.hardware
@pytest.mark.asyncio
async def test_persistence_init_fails_on_corrupt_db(tmp_path: Path) -> None:
    """Ante una BD persistida corrupta, la inicialización falla (fail-closed).

    El lifespan de ``main.py`` captura este error y lo relanza, de modo que el
    backend no entra en READY y systemd reinicia (en lugar de arrancar
    desprotegido). Aquí verificamos el eslabón base: ``Persistence.init()``
    lanza excepción ante un fichero que no es SQLite.

    Es seguro: trabaja sobre una ruta temporal, nunca sobre la BD real.
    """
    try:
        from backend.app.services.persistence import Persistence
    except ImportError as exc:
        pytest.skip(f"backend.app.services.persistence no importable: {exc}")

    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"esto no es una base de datos sqlite\n")

    db = Persistence(str(corrupt))
    with pytest.raises(sqlite3.Error):
        await db.init()


@pytest.mark.hardware
@pytest.mark.asyncio
async def test_persistence_init_creates_absent_db(tmp_path: Path) -> None:
    """Una BD ausente (no corrupta) se crea y queda healthy (arranque limpio).

    Contrasta con el fail-closed: "ausente" es el caso sano de primera
    ejecución (el backend crea el esquema y arranca), mientras que "corrupta"
    es el caso que debe abortar el arranque.
    """
    try:
        from backend.app.services.persistence import Persistence
    except ImportError as exc:
        pytest.skip(f"backend.app.services.persistence no importable: {exc}")

    fresh = tmp_path / "fresh.db"
    db = Persistence(str(fresh))
    try:
        await db.init()
        assert await db.is_healthy() is True
    finally:
        with contextlib.suppress(Exception):
            await db.close()


# ── Integridad de arranque (proxy de "apagado brusco") ─────────


@pytest.mark.hardware
def test_systemd_units_active() -> None:
    """Las unidades systemd del backend y del display están active (running)."""
    for service in (_BACKEND_SERVICE, _DISPLAY_SERVICE):
        proc = _run_command(["systemctl", "is-active", service], timeout=10.0)
        if proc is None:
            pytest.skip("systemctl no disponible (no bajo systemd)")
        state = proc.stdout.strip()
        if proc.returncode != 0 or state != "active":
            pytest.fail(f"{service}: estado inesperado {state!r} (rc={proc.returncode})")


@pytest.mark.hardware
def test_backend_watchdog_no_restarts() -> None:
    """El watchdog del backend no ha provocado reinicios (NRestarts=0)."""
    proc = _run_command(
        ["systemctl", "show", _BACKEND_SERVICE, "-p", "NRestarts"], timeout=10.0
    )
    if proc is None:
        pytest.skip("systemctl no disponible (no bajo systemd)")
    if proc.returncode != 0:
        pytest.skip(f"systemctl show falló (rc={proc.returncode}): {proc.stderr.strip()}")
    line = proc.stdout.strip()
    if "=" not in line:
        pytest.skip(f"No se pudo leer NRestarts de systemd: {line!r}")
    value = line.split("=", 1)[1].strip()
    if value != "0":
        pytest.fail(f"{_BACKEND_SERVICE} fue reiniciado {value} veces (NRestarts!=0)")


@pytest.mark.hardware
def test_journal_no_crash_loop_current_boot() -> None:
    """El journal del boot actual no muestra un bucle de reinicios del backend.

    Comprueba dos cosas: que journalctl está disponible y es legible, y que en
    el boot actual el backend arrancó sin el mensaje crítico de fail-closed
    ("SQLite es esencial") y con al menos un arranque de la unidad. El recuento
    exacto de reinicios lo cubre ``test_backend_watchdog_no_restarts``.
    """
    boots = _run_command(["journalctl", "--list-boots", "--no-pager"], timeout=15.0)
    if boots is None or boots.returncode != 0:
        pytest.skip("journalctl no disponible o journal no legible")

    journal = _run_command(
        ["journalctl", "-u", _BACKEND_SERVICE, "-b", "--no-pager"], timeout=15.0
    )
    if journal is None or journal.returncode != 0:
        pytest.skip(f"No se pudo leer el journal de {_BACKEND_SERVICE}")
    assert "SQLite es esencial" not in journal.stdout
    assert journal.stdout.count("Started rpi-hmi-backend.service") >= 1
