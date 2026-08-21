"""Dependencias reutilizables de FastAPI.

Proporciona dos dependencias de autenticacion basadas en el patron de
``_verify_api_key`` (antes duplicado en ``ssh.py``/``deploy.py``), unificadas
y configurables segun ``settings.SECURITY_MODE``:

- ``require_admin_api_key`` (respeta ``SECURITY_MODE``): para mutadores HMI/red.
- ``require_admin_api_key_always`` (exige key siempre): para ``/admin/*``.

En ``local`` (default) no se exige autenticacion (HMI de prototipo domestico);
en ``protected`` se exige autenticacion excepto para clientes loopback (el
display fisico local), que quedan exentos para no romper el HMI táctil.

La autenticacion acepta **o bien** el header ``X-API-Key`` igual a
``settings.admin_api_key`` (scripts/M2M) **o bien** una cookie de sesion valida
emitida por ``POST /api/auth/login`` (navegador). Ver ``backend/app/api/auth.py``.

Pensada para proteger endpoints que mutan hardware/red (p. ej. cambio de IP).
Los endpoints de solo lectura pueden seguir siendo publicos.
"""

from __future__ import annotations

import logging
import secrets as _secrets

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from backend.app.api.auth import get_session_token_from_cookies, session_manager
from backend.app.config import settings
from backend.app.services.security_manager import security_manager

logger = logging.getLogger("backend.api.deps")

# ── Autenticacion por API Key / cookie de sesion ───────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Hosts de loopback considerados de confianza en modo ``protected``.
# El display fisico (Pygame) llama a la REST local (localhost:8000) desde la
# propia Pi, por lo que estas conexiones no requieren X-API-Key.
_LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")


def is_loopback_host(host: str | None) -> bool:
    """Devuelve True si el host del cliente es loopback (display local)."""
    return (host or "").lower() in _LOOPBACK_HOSTS


def _is_loopback_client(request: Request) -> bool:
    """Devuelve True si la peticion proviene de loopback (cliente local)."""
    client = getattr(request, "client", None)
    return client is not None and is_loopback_host(client.host)


def _has_valid_session(request: Request) -> bool:
    """Devuelve True si la peticion trae una cookie de sesion valida."""
    token = get_session_token_from_cookies(request.headers.get("cookie"))
    return session_manager.is_valid(token)


def require_admin_api_key(
    request: Request,
    api_key: str | None = Security(_api_key_header),
) -> None:
    """Exige autenticacion solo si la contraseña del panel está activada.

    Si ``security_manager.is_enabled()`` es False no exige autenticacion y
    retorna ``None`` (equivale al antiguo ``SECURITY_MODE=local``). Si está
    activada (equivale a ``protected``):
    - Las peticiones desde loopback (127.0.0.1 / ::1 / localhost) se aceptan
      sin credenciales: es el display fisico (Pygame) que corre en la propia Pi.
    - La cookie de sesion valida se comprueba ANTES del chequeo de
      ``ADMIN_API_KEY`` vacía: el panel web debe funcionar aunque
      ``ADMIN_API_KEY`` esté vacía.
    - El resto debe autenticarse con ``X-API-Key`` (scripts/M2M).

    Se usa en los mutadores HMI (LED/button/display/red).

    Raises:
        HTTPException 401: Si no hay credencial valida, o si no hay key
            configurada estando activada la seguridad.
    """
    if not security_manager.is_enabled():
        return None

    if _is_loopback_client(request):
        return None

    if _has_valid_session(request):
        return None

    if not settings.admin_api_key:
        logger.critical("Seguridad del panel activada pero ADMIN_API_KEY vacia")
        raise HTTPException(
            status_code=401,
            detail="API administrativa no configurada. Establece ADMIN_API_KEY en .env",
        )

    _require_matching_key(api_key)

    return None


def require_admin_api_key_always(
    request: Request,
    api_key: str | None = Security(_api_key_header),
) -> None:
    """Exige autenticacion SIEMPRE, independiente de ``SECURITY_MODE``.

    Se usa en los endpoints ``/admin/*`` (SSH y deploy). A diferencia de
    ``require_admin_api_key``, no respeta el modo local. Acepta ``X-API-Key``
    (scripts/M2M) o cookie de sesion valida (navegador).

    Raises:
        HTTPException 503: Si no hay ``ADMIN_API_KEY`` configurada.
        HTTPException 401: Si no hay credencial valida.
    """
    if not settings.admin_api_key:
        logger.warning("ADMIN_API_KEY no configurada en .env")
        raise HTTPException(
            status_code=503,
            detail="API administrativa no configurada. Establece ADMIN_API_KEY en .env",
        )

    if _has_valid_session(request):
        return None

    _require_matching_key(api_key)

    return None


def _require_matching_key(api_key: str | None) -> None:
    """Nucleo compartido: compara ``api_key`` con ``settings.admin_api_key``.

    Raises:
        HTTPException 401: Si la key falta o no coincide (comparacion con
            ``secrets.compare_digest`` para evitar timing attacks).
    """
    if not _secrets.compare_digest(api_key or "", settings.admin_api_key):
        raise HTTPException(status_code=401, detail="API key invalida")
