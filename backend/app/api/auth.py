"""Autenticacion del panel web mediante session-cookie HttpOnly.

Sustituye la exposicion de ``ADMIN_API_KEY`` en el bundle del navegador
(antiguo ``VITE_API_KEY``) por un flujo de login explicito:

1. ``POST /api/auth/login`` recibe la contraseña del panel en el body JSON, la
   valida contra ``security_manager.verify_password`` (PBKDF2 persistido) y
   emite una cookie de sesion HttpOnly.
2. ``POST /api/auth/logout`` revoca la sesion en memoria y borra la cookie.
3. Las dependencias de auth (``deps.py``) y el handshake WebSocket (``ws.py``)
   aceptan, ademas de ``X-API-Key`` (scripts/M2M), una cookie de sesion valida
   (navegador).
4. ``GET/POST /api/auth/security`` y ``POST /api/auth/password`` gestionan la
   contraseña del panel (activar/desactivar/cambiar), persistida en SQLite.

La sesion es **en memoria** (dict ``token -> expiracion``). El token esta
firmado con HMAC-SHA256 (stdlib ``hmac`` + ``secrets``) usando una clave de
firma derivada de ``ADMIN_API_KEY`` y un secreto aleatorio por arranque: asi
cada reinicio invalida todas las sesiones anteriores y rotar ``ADMIN_API_KEY``
tambien las invalida. No se anaden dependencias nuevas.

Limitacion LAN: la cookie se emite con ``Secure`` solo si el backend recibe
HTTPS (``request.url.scheme == "https"`` o cabecera ``X-Forwarded-Proto``).
En una LAN de confianza sin TLS la cookie viaja en claro; ver ``docs/SECURITY.md``.

Anti brute-force: ``POST /api/auth/login`` aplica un rate-limit de ventana fija
en memoria por IP de cliente (``LoginRateLimiter``). Se cuentan SOLO los intentos
fallidos; superado ``LOGIN_MAX_ATTEMPTS`` dentro de ``LOGIN_WINDOW_SECONDS`` el
endpoint devuelve 429, y un login correcto reinicia el contador de esa IP.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import secrets as _secrets
import threading
import time
from collections.abc import Callable, Mapping

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.app.config import settings
from backend.app.models.security import (
    ChangePasswordRequest,
    SecurityStatus,
    SecurityToggleRequest,
)
from backend.app.services.security_manager import security_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

#: Nombre de la cookie de sesion enviada al navegador.
SESSION_COOKIE_NAME = "rpi_hmi_session"

#: Secreto aleatorio por arranque, mezclado con ADMIN_API_KEY para firmar tokens.
_BOOT_SECRET = _secrets.token_bytes(32)


def _signing_key() -> bytes:
    """Deriva la clave HMAC de firma a partir de ``ADMIN_API_KEY`` y el boot secret.

    Returns:
        Clave binaria de 32 bytes para HMAC-SHA256.
    """
    return hmac.new(
        _BOOT_SECRET,
        settings.admin_api_key.encode("utf-8"),
        hashlib.sha256,
    ).digest()


def _b64url(data: bytes) -> str:
    """Codifica bytes en base64url sin relleno (seguro en cookies)."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    """Decodifica base64url sin relleno; tolera valores malformados."""
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


class SessionManager:
    """Gestion de sesiones de panel web en memoria.

    Mantiene un dict ``token -> expiracion`` protegido con un lock (las
    dependencias de FastAPI pueden correr en hilos distintos). El token
    entregado al navegador es ``sid.hmac_sid`` (ambos base64url), de modo que
    solo este proceso puede emitir tokens validos y la validacion no depende
    exclusivamente de la presencia en el dict.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._sessions: dict[str, float] = {}
        self._lock = threading.Lock()

    @property
    def ttl_seconds(self) -> int:
        """TTL configurado para las sesiones nuevas."""
        return self._ttl_seconds

    def issue(self) -> str:
        """Emite un token de sesion firmado y registra su expiracion.

        Returns:
            Token de sesion (``sid.hmac`` en base64url).
        """
        sid = _secrets.token_bytes(32)
        sig = hmac.new(_signing_key(), sid, hashlib.sha256).digest()
        token = f"{_b64url(sid)}.{_b64url(sig)}"
        expires_at = time.monotonic() + self._ttl_seconds
        with self._lock:
            self._sessions[token] = expires_at
        return token

    def revoke(self, token: str) -> None:
        """Elimina una sesion del almacen (logout o cierre)."""
        with self._lock:
            self._sessions.pop(token, None)

    def clear(self) -> None:
        """Vacia todas las sesiones (util en tests)."""
        with self._lock:
            self._sessions.clear()

    def is_valid(self, token: str | None) -> bool:
        """Devuelve True si ``token`` es una sesion firmada y no expirada.

        Args:
            token: Token completo ``sid.hmac``; si es ``None`` o malformado,
                devuelve False.

        Returns:
            True solo si la firma HMAC coincide y la sesion sigue viva.
        """
        if not token or "." not in token:
            return False
        sid_part, _, sig_part = token.partition(".")
        try:
            sid = _b64url_decode(sid_part)
            provided_sig = _b64url_decode(sig_part)
        except (ValueError, binascii.Error):
            return False
        expected_sig = hmac.new(_signing_key(), sid, hashlib.sha256).digest()
        if not hmac.compare_digest(provided_sig, expected_sig):
            return False
        with self._lock:
            expires_at = self._sessions.get(token)
            if expires_at is None:
                return False
            if expires_at <= time.monotonic():
                self._sessions.pop(token, None)
                return False
            return True


#: Singleton de sesiones; TTL configurado via ``SESSION_TTL_SECONDS``.
session_manager = SessionManager(settings.session_ttl_seconds)


class LoginRateLimiter:
    """Rate-limiter de ventana fija por IP para intentos fallidos de login.

    Ventana fija por direccion IP de cliente: dentro de ``window_seconds`` se
    cuentan SOLO los intentos fallidos; al alcanzar ``max_attempts`` el siguiente
    intento se bloquea (el endpoint devuelve 429). Un login correcto reinicia el
    contador de esa IP. Todo en memoria y sin dependencias nuevas (stdlib
    ``threading`` + ``time``).

    Args:
        max_attempts: Intentos fallidos permitidos por ventana.
        window_seconds: Duracion de la ventana en segundos.
        clock: Callable que devuelve el tiempo monotonic en segundos. Se inyecta
            para poder controlar el reloj en tests (default ``time.monotonic``).
    """

    def __init__(
        self,
        max_attempts: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._clock = clock
        self._failures: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    @property
    def max_attempts(self) -> int:
        """Numero de intentos fallidos permitidos por ventana."""
        return self._max_attempts

    @property
    def window_seconds(self) -> int:
        """Duracion de la ventana de rate-limit en segundos."""
        return self._window_seconds

    def is_blocked(self, ip: str) -> bool:
        """Devuelve True si ``ip`` debe ser bloqueada en este momento.

        Args:
            ip: Direccion IP del cliente.

        Returns:
            True si la IP acumula ``max_attempts`` o mas fallos dentro de la
            ventana vigente. Una ventana expirada se descarta y no bloquea.
        """
        with self._lock:
            entry = self._failures.get(ip)
            if entry is None:
                return False
            window_start, count = entry
            if self._clock() - window_start >= self._window_seconds:
                self._failures.pop(ip, None)
                return False
            return count >= self._max_attempts

    def register_failure(self, ip: str) -> None:
        """Registra un intento fallido de login para ``ip``.

        Args:
            ip: Direccion IP del cliente.
        """
        with self._lock:
            now = self._clock()
            entry = self._failures.get(ip)
            if entry is None or now - entry[0] >= self._window_seconds:
                self._failures[ip] = (now, 1)
            else:
                self._failures[ip] = (entry[0], entry[1] + 1)

    def reset(self, ip: str) -> None:
        """Reinicia el contador de ``ip`` (login correcto).

        Args:
            ip: Direccion IP del cliente.
        """
        with self._lock:
            self._failures.pop(ip, None)

    def clear(self) -> None:
        """Vacia todo el estado (util en tests)."""
        with self._lock:
            self._failures.clear()


#: Singleton de rate-limit; limites configurados via settings.
rate_limiter = LoginRateLimiter(
    max_attempts=settings.login_max_attempts,
    window_seconds=settings.login_window_seconds,
)


def _client_ip(request: Request) -> str:
    """Devuelve la IP del cliente de la peticion.

    Args:
        request: Peticion HTTP entrante.

    Returns:
        Host del cliente (``request.client.host``) o ``"unknown"`` si no esta
        disponible (p. ej. en algunos entornos de test sin socket).
    """
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def get_session_token_from_cookies(cookie_header: str | None) -> str | None:
    """Extrae el token de sesion de una cabecera ``Cookie``.

    Args:
        cookie_header: Valor crudo de la cabecera ``Cookie`` (p. ej.
            ``"rpi_hmi_session=abc; other=1"``).

    Returns:
        Token de sesion o ``None`` si la cookie no esta presente.
    """
    if not cookie_header:
        return None
    for pair in cookie_header.split(";"):
        name, sep, value = pair.partition("=")
        if sep and name.strip() == SESSION_COOKIE_NAME:
            return value.strip() or None
    return None


def get_session_token_from_headers(headers: Mapping[str, str] | None) -> str | None:
    """Lee el token de sesion de un Mapping de headers (case-insensitive).

    Args:
        headers: Mapping de cabeceras (p. ej. ``websocket.headers``).

    Returns:
        Token de sesion o ``None`` si la cookie no esta presente.
    """
    if not isinstance(headers, Mapping):
        return None
    for key, value in headers.items():
        if str(key).lower() == "cookie":
            return get_session_token_from_cookies(str(value))
    return None


def _request_is_https(request: Request) -> bool:
    """Devuelve True si la peticion llega por HTTPS (directo o tras proxy)."""
    if request.url.scheme == "https":
        return True
    forwarded = request.headers.get("x-forwarded-proto", "")
    return forwarded.split(",")[0].strip().lower() == "https"


class LoginRequest(BaseModel):
    """Body de ``POST /api/auth/login``: la contraseña del panel web."""

    password: str = Field(..., min_length=1, description="Contraseña del panel web")


@router.post("/login")
async def login(request: Request, body: LoginRequest) -> JSONResponse:
    """Valida la contraseña del panel y emite la cookie de sesión HttpOnly.

    Valida ``body.password`` contra ``security_manager.verify_password``
    (contraseña persistida en SQLite, por defecto ``1234``), no contra
    ``settings.admin_api_key``. Aplica rate-limiting por IP (ventana fija)
    contando solo intentos fallidos: superado ``LOGIN_MAX_ATTEMPTS`` dentro de
    ``LOGIN_WINDOW_SECONDS`` devuelve 429; un login correcto reinicia el
    contador. La comparación es en tiempo constante (PBKDF2 + compare_digest).

    Returns:
        JSON ``{"authenticated": true}`` y cabecera ``Set-Cookie`` con la sesión.
        En caso de bloqueo por rate-limit, ``429`` con ``{"detail": ...}``.
    """
    ip = _client_ip(request)
    if rate_limiter.is_blocked(ip):
        logger.warning("Login bloqueado por rate-limit desde %s", ip)
        return JSONResponse(
            status_code=429,
            content={"detail": "Demasiados intentos fallidos. Intenta de nuevo mas tarde."},
        )

    if not security_manager.verify_password(body.password):
        rate_limiter.register_failure(ip)
        logger.warning("Login rechazado (contraseña inválida) desde %s", ip)
        return JSONResponse(status_code=401, content={"detail": "Contraseña inválida"})

    rate_limiter.reset(ip)
    token = session_manager.issue()
    response = JSONResponse(content={"authenticated": True})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=session_manager.ttl_seconds,
        httponly=True,
        samesite="strict",
        secure=_request_is_https(request),
        path="/",
    )
    logger.info("Login correcto; sesion emitida")
    return response


@router.post("/logout")
async def logout(request: Request) -> JSONResponse:
    """Revoca la sesion actual y borra la cookie del navegador.

    Returns:
        JSON ``{"authenticated": false}`` y cabecera ``Set-Cookie`` de borrado.
    """
    token = get_session_token_from_cookies(request.headers.get("cookie"))
    if token:
        session_manager.revoke(token)
    response = JSONResponse(content={"authenticated": False})
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="strict",
        secure=_request_is_https(request),
    )
    return response


@router.get("/status")
async def auth_status(request: Request) -> JSONResponse:
    """Estado de autenticacion publico para que el frontend decida mostrar login.

    No revela la contraseña; solo indica el ``security_mode`` (derivado del flag
    runtime ``security_manager.is_enabled()``) y si la peticion trae una cookie
    de sesion valida.

    Returns:
        JSON ``{"security_mode": ..., "authenticated": ...}``.
    """
    token = get_session_token_from_cookies(request.headers.get("cookie"))
    enabled = security_manager.is_enabled()
    return JSONResponse(
        content={
            "security_mode": "protected" if enabled else "local",
            "authenticated": (not enabled) or session_manager.is_valid(token),
        }
    )


def _authorize_security_change(request: Request, current: str | None) -> bool:
    """Decide si una petición de cambio de seguridad está autorizada.

    Permite el cambio si se cumple **alguna** de estas condiciones:
    (a) la petición trae una cookie de sesión válida, (b) la cabecera
    ``X-API-Key`` coincide con ``settings.admin_api_key`` (solo si está
    configurada), o (c) ``current`` verifica contra la contraseña almacenada.

    Args:
        request: Petición HTTP entrante.
        current: Contraseña actual proporcionada (puede ser ``None``).

    Returns:
        True si la petición está autorizada; False en caso contrario.
    """
    token = get_session_token_from_cookies(request.headers.get("cookie"))
    if session_manager.is_valid(token):
        return True

    api_key = request.headers.get("x-api-key")
    if settings.admin_api_key and api_key and _secrets.compare_digest(
        api_key, settings.admin_api_key
    ):
        return True

    return current is not None and security_manager.verify_password(current)


@router.get("/security")
async def get_security() -> SecurityStatus:
    """Devuelve el estado público de la seguridad del panel web.

    Returns:
        ``SecurityStatus`` con ``enabled`` e ``is_default``.
    """
    return SecurityStatus(
        enabled=security_manager.is_enabled(),
        is_default=security_manager.is_default_password(),
    )


@router.post("/security")
async def set_security(request: Request, body: SecurityToggleRequest) -> JSONResponse:
    """Activa/desactiva la contraseña del panel web.

    La autorización usa ``_authorize_security_change`` (cookie de sesión,
    ``X-API-Key`` o ``current``). Aplica rate-limit sobre los fallos.

    Si se intenta **activar** la protección con la contraseña de fábrica
    (``1234``) aún sin cambiar, devuelve ``409``: el usuario debe establecer
    una contraseña personalizada antes de activar.

    Returns:
        ``SecurityStatus`` actualizado, o ``401``/``409``/``429`` según
        corresponda.
    """
    ip = _client_ip(request)
    if rate_limiter.is_blocked(ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Demasiados intentos fallidos. Intenta de nuevo mas tarde."},
        )

    if not _authorize_security_change(request, body.current):
        rate_limiter.register_failure(ip)
        logger.warning("Cambio de seguridad rechazado desde %s", ip)
        return JSONResponse(status_code=401, content={"detail": "No autorizado"})

    if body.enabled and security_manager.is_default_password():
        return JSONResponse(
            status_code=409,
            content={
                "detail": (
                    "Debes cambiar la contraseña de fábrica (1234) "
                    "antes de activar la protección."
                )
            },
        )

    rate_limiter.reset(ip)
    await security_manager.set_enabled(body.enabled)
    return JSONResponse(
        content={
            "enabled": security_manager.is_enabled(),
            "is_default": security_manager.is_default_password(),
        }
    )


@router.post("/password")
async def change_password(request: Request, body: ChangePasswordRequest) -> JSONResponse:
    """Cambia la contraseña del panel web y revoca todas las sesiones.

    Requiere que ``current`` verifique contra la contraseña almacenada
    (siempre). Al éxito, persiste la nueva contraseña y llama a
    ``session_manager.clear()`` para forzar re-login. Aplica rate-limit.

    Returns:
        JSON ``{"success": true}``, o ``401``/``429`` según corresponda.
    """
    ip = _client_ip(request)
    if rate_limiter.is_blocked(ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Demasiados intentos fallidos. Intenta de nuevo mas tarde."},
        )

    if not security_manager.verify_password(body.current):
        rate_limiter.register_failure(ip)
        logger.warning("Cambio de contraseña rechazado (current inválido) desde %s", ip)
        return JSONResponse(status_code=401, content={"detail": "Contraseña actual incorrecta"})

    rate_limiter.reset(ip)
    await security_manager.set_password(body.new)
    session_manager.clear()
    return JSONResponse(content={"success": True})
