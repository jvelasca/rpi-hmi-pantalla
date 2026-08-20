"""Dependencias reutilizables de FastAPI.

Proporciona ``require_admin_api_key``, una unica dependencia de autenticacion
que replica el patron de ``_verify_api_key`` de ``ssh.py``/``deploy.py`` y lo
hace configurable segun ``settings.SECURITY_MODE``:

- ``local`` (default): no exige autenticacion (HMI de prototipo domestico).
- ``protected``: exige el header ``X-API-Key`` igual a ``settings.admin_api_key``.

Pensada para proteger endpoints que mutan hardware/red (p. ej. cambio de IP).
Los endpoints de solo lectura pueden seguir siendo publicos.
"""

from __future__ import annotations

import logging
import secrets as _secrets
from typing import Optional

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from backend.app.config import settings

logger = logging.getLogger("backend.api.deps")

# ── Autenticacion por API Key ─────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_admin_api_key(api_key: Optional[str] = Security(_api_key_header)) -> None:
    """Exige API key unicamente en modo ``protected``.

    En ``SECURITY_MODE == "local"`` no exige autenticacion y retorna ``None``.
    En ``SECURITY_MODE == "protected"`` exige ``X-API-Key == settings.admin_api_key``.

    Raises:
        HTTPException 401: Si la key falta/no coincide, o si no hay key
            configurada estando en modo protegido.
    """
    if settings.security_mode == "local":
        return None

    if not settings.admin_api_key:
        logger.critical("SECURITY_MODE=protected pero ADMIN_API_KEY vacia")
        raise HTTPException(
            status_code=401,
            detail="API administrativa no configurada. Establece ADMIN_API_KEY en .env",
        )

    if not _secrets.compare_digest(api_key or "", settings.admin_api_key):
        raise HTTPException(status_code=401, detail="API key invalida")

    return None
