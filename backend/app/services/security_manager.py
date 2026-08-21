"""SecurityManager — Estado runtime de la contraseña del panel web.

Singleton con un estado **cambiable en caliente y persistido en SQLite**:

- ``is_enabled()`` controla si el login del panel y la protección de los
  mutadores HMI están activos. El estado por defecto es **desactivado**
  (la web no pide contraseña al cargar); el estado real es ``password_enabled``
  persistido en SQLite, leído por ``security_manager.load()``.
- ``verify_password()`` valida la contraseña del panel contra el hash
  persistido (por defecto ``"1234"``).
- ``set_enabled``/``set_password`` persisten el cambio en SQLite y actualizan
  la cache en memoria.

La cache en memoria se protege con ``threading.Lock`` porque los checks de
``deps.py`` y ``ws.py`` son síncronos y pueden ejecutarse en hilos distintos.

Separación de responsabilidades: este manager gestiona la **contraseña del
panel web**; ``settings.admin_api_key`` sigue siendo la clave M2M
(``X-API-Key`` y ``/admin/*``) y no cambia.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from backend.app.services.password_hash import (
    DEFAULT_PASSWORD,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)

__all__ = ["SecurityManager", "security_manager"]


class SecurityManager:
    """Cache y persistencia de la configuración de seguridad del panel web.

    ``load()`` falla cerrado: si no puede leer ``security_settings`` desde
    SQLite (o los datos son inválidos), propaga el error en lugar de dejar el
    estado desprotegido.

    Attributes:
        _lock: Lock para proteger la cache en memoria.
        _enabled: Si la contraseña del panel está activada.
        _password_hash: Hash PBKDF2 de la contraseña actual.
        _persistence: Instancia de ``Persistence`` (opcional; se fija en
            ``load``). Si es ``None``, los setters solo actualizan la cache.
    """

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._enabled: bool = False
        self._password_hash: str = hash_password(DEFAULT_PASSWORD)
        self._persistence: Any = None

    def is_enabled(self) -> bool:
        """Devuelve True si la contraseña del panel está activada.

        Returns:
            Estado actual de ``password_enabled``.
        """
        with self._lock:
            return self._enabled

    def verify_password(self, plain: str) -> bool:
        """Valida una contraseña en texto plano contra el hash actual.

        Args:
            plain: Contraseña en texto plano.

        Returns:
            True si coincide con el hash almacenado.
        """
        with self._lock:
            stored = self._password_hash
        return verify_password(plain, stored)

    def is_default_password(self) -> bool:
        """Devuelve True si la contraseña actual es la de fábrica (``1234``).

        Returns:
            True si ``verify_password(DEFAULT_PASSWORD)`` es True.
        """
        return self.verify_password(DEFAULT_PASSWORD)

    async def load(self, persistence: Any) -> None:
        """Lee la configuración desde SQLite y actualiza la cache.

        Comportamiento **fail-closed**: cualquier error de lectura de la BD
        (``get_security_settings``) o de estructura de los datos (``KeyError``/
        ``TypeError``) se propaga en lugar de dejarse tragar. Así un sistema
        previamente protegido nunca arranca desprotegido por un fallo de
        persistencia.

        Args:
            persistence: Instancia de ``Persistence`` inicializada.

        Raises:
            Exception: Si no se puede leer ``security_settings`` o los datos
                devueltos son inválidos.
        """
        self._persistence = persistence
        data = await persistence.get_security_settings()
        password_hash = data["password_hash"]
        password_enabled = bool(data["password_enabled"])

        with self._lock:
            self._password_hash = password_hash
            self._enabled = password_enabled
        logger.info("SecurityManager cargado: enabled=%s", password_enabled)

    async def set_enabled(self, enabled: bool) -> None:
        """Activa/desactiva la contraseña del panel y persiste el cambio.

        Args:
            enabled: Nuevo estado del flag ``password_enabled``.
        """
        with self._lock:
            self._enabled = enabled
            password_hash = self._password_hash
        if self._persistence is not None:
            await self._persistence.save_security_settings(password_hash, enabled)
        logger.info("Seguridad del panel %s", "activada" if enabled else "desactivada")

    async def set_password(self, new: str) -> None:
        """Cambia la contraseña del panel y persiste el nuevo hash.

        Args:
            new: Nueva contraseña en texto plano.
        """
        new_hash = hash_password(new)
        with self._lock:
            self._password_hash = new_hash
            enabled = self._enabled
        if self._persistence is not None:
            await self._persistence.save_security_settings(new_hash, enabled)
        logger.info("Contraseña del panel actualizada")

    def reset(self) -> None:
        """Devuelve el estado a los defaults (util en tests).

        Restaura ``_enabled`` a ``False`` (la seguridad del panel queda
        desactivada por defecto), el hash de ``DEFAULT_PASSWORD`` y desvincula
        la referencia de persistencia para evitar contaminación entre tests.
        """
        with self._lock:
            self._enabled = False
            self._password_hash = hash_password(DEFAULT_PASSWORD)
            self._persistence = None


#: Instancia única global del SecurityManager.
security_manager = SecurityManager()
