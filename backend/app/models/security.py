"""Modelos Pydantic para la gestión de seguridad del panel web.

Define las entidades de entrada/salida de los endpoints de seguridad
(``GET/POST /api/auth/security`` y ``POST /api/auth/password``) y el cuerpo
de login del panel. Tipos TypeScript equivalentes: frontend/src/types/api.ts.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SecurityStatus(BaseModel):
    """Estado público de la seguridad del panel web.

    Attributes:
        enabled: True si la contraseña del panel está activada.
        is_default: True si la contraseña actual es la de fábrica (``1234``).
    """

    enabled: bool = Field(description="Contraseña del panel activada")
    is_default: bool = Field(description="La contraseña es la de fábrica (1234)")


class SecurityToggleRequest(BaseModel):
    """Body de ``POST /api/auth/security`` (activar/desactivar).

    Attributes:
        enabled: Nuevo estado deseado del flag de contraseña.
        current: Contraseña actual (opcional); se usa como credencial de
            autorización cuando no hay cookie de sesión ni ``X-API-Key``.
    """

    enabled: bool = Field(description="Activar o desactivar la contraseña")
    current: str | None = Field(default=None, description="Contraseña actual (autorización)")


class ChangePasswordRequest(BaseModel):
    """Body de ``POST /api/auth/password`` (cambio de contraseña).

    Attributes:
        current: Contraseña actual (obligatoria, siempre se verifica).
        new: Nueva contraseña (mínimo 8 caracteres).
    """

    current: str = Field(description="Contraseña actual")
    new: str = Field(min_length=8, description="Nueva contraseña (mín. 8 caracteres)")
