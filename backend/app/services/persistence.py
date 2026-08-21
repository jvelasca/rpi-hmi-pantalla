"""Capa de persistencia SQLite asincrona.

Gestiona una base de datos SQLite local con aiosqlite para:
- Guardar y restaurar el estado del LED
- Guardar y restaurar el contador de pulsaciones del boton
- Registrar un log de eventos (cambios de estado)

La BD se crea automaticamente en la primera ejecucion (migracion inline).

Uso:
    from backend.app.services.persistence import Persistence

    db = Persistence("data/state.db")
    await db.init()
    await db.save_led(state=True, gpio_pin=17)
    count = await db.get_button_count()
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)


class Persistence:
    """Capa de persistencia SQLite para el estado del sistema.

    Thread-safe: las operaciones usan aiosqlite (async, single-connection)
    y deben llamarse desde dentro del event loop.

    Attributes:
        db_path: Ruta al archivo .db.
        _conn: Conexion aiosqlite (None si no inicializada).
    """

    MAX_EVENT_LOG_ROWS = 10000

    # Migraciones incrementales. Cada item es (version, nombre, metodo).
    # El metodo devuelve None; runner comprueba que solo se aplica si
    # version > version actual registrada en schema_version.
    _MIGRATIONS: list[tuple[int, str, str]] = [
        (1, "schema_inicial", "_migration_001"),
        (2, "indice_event_log", "_migration_002"),
        (3, "security_settings", "_migration_003"),
    ]

    def __init__(self, db_path: str) -> None:
        self.db_path: str = db_path
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        """Inicializa la BD: crea directorio, tablas y migra si es necesario.

        Debe llamarse UNA vez durante el arranque de la aplicacion.
        """
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

        # Habilitar WAL para mejor concurrencia
        await self._conn.execute("PRAGMA journal_mode=WAL")

        # La tabla de versionado debe existir antes de ejecutar migraciones.
        await self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
        )

        # Compatibilidad con BD existente: si hay tablas legacy sin registro de
        # version, NO se marca version a mano. Las migraciones son idempotentes
        # (_migration_001 usa CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE),
        # por lo que se ejecutan igualmente y crean las tablas que falten
        # (p. ej. display_settings) sin perder los datos existentes.
        if await self._has_legacy_tables() and await self._get_schema_version() == 0:
            logger.info("BD existente detectada: se aplicaran migraciones idempotentes")

        # Ejecutar migraciones pendientes de forma incremental.
        for version, _name, method_name in self._MIGRATIONS:
            if version <= await self._get_schema_version():
                continue
            method = getattr(self, method_name)
            await method()
            await self._conn.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (version,)
            )
            await self._conn.commit()
            logger.info("Migracion %s aplicada (version=%d)", method_name, version)

        await self._conn.commit()
        logger.info("Persistencia inicializada: %s", self.db_path)

    async def _has_legacy_tables(self) -> bool:
        """True si las tablas del esquema original ya existen."""
        if not self._conn:
            return False
        cursor = await self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='led_state'"
        )
        row = await cursor.fetchone()
        return row is not None

    async def _get_schema_version(self) -> int:
        """Devuelve la version de esquema registrada (0 si no hay)."""
        if not self._conn:
            return 0
        cursor = await self._conn.execute("SELECT MAX(version) FROM schema_version")
        row = await cursor.fetchone()
        if row is None or row[0] is None:
            return 0
        return int(row[0])

    async def get_schema_version(self) -> int:
        """Version de esquema actual (API publica de introspeccion)."""
        return await self._get_schema_version()

    async def _migration_001(self) -> None:
        """Esquema inicial: tablas led_state, button_state, event_log y display_settings."""
        assert self._conn is not None
        # NOTA: gpio_pin NO se almacena en BD — la fuente unica de verdad
        #       del hardware es devices.yaml, nunca SQLite.
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS led_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS button_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                press_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT
            );

            CREATE TABLE IF NOT EXISTS display_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                font_family TEXT NOT NULL DEFAULT 'dejavu',
                text_size TEXT NOT NULL DEFAULT 'medium',
                updated_at TEXT NOT NULL
            );

            -- Insertar filas iniciales si no existen
            INSERT OR IGNORE INTO led_state (id, state, updated_at)
                VALUES (1, 0, datetime('now'));

            INSERT OR IGNORE INTO button_state (id, press_count, updated_at)
                VALUES (1, 0, datetime('now'));

            INSERT OR IGNORE INTO display_settings (id, font_family, text_size, updated_at)
                VALUES (1, 'dejavu', 'medium', datetime('now'));
        """)

    async def _migration_002(self) -> None:
        """Anade indice sobre event_log.timestamp para consultas por fecha."""
        assert self._conn is not None
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_event_log_timestamp ON event_log (timestamp)"
        )

    async def _migration_003(self) -> None:
        """Crea la tabla ``security_settings`` y siembra la fila inicial.

        Guarda el hash PBKDF2 de la contraseña del panel y el flag de
        activación. La fila inicial usa la contraseña de fábrica (``1234``)
        y ``password_enabled=1`` solo si ``settings.security_mode`` es
        ``protected`` (equivale al estado previo a la migración).
        """
        assert self._conn is not None
        # Import dentro del método para evitar imports circulares al
        # cargar el módulo (config/security no dependen de persistence).
        from backend.app.config import settings
        from backend.app.services.password_hash import DEFAULT_PASSWORD, hash_password

        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS security_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                password_hash TEXT NOT NULL,
                password_enabled INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );
        """)

        default_hash = hash_password(DEFAULT_PASSWORD)
        enabled = 1 if settings.security_mode == "protected" else 0
        await self._conn.execute(
            "INSERT OR IGNORE INTO security_settings "
            "(id, password_hash, password_enabled, updated_at) "
            "VALUES (1, ?, ?, datetime('now'))",
            (default_hash, enabled),
        )

    async def close(self) -> None:
        """Cierra la conexion a la BD."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Persistencia cerrada")

    # ── LED ────────────────────────────────────────────────────

    async def get_led(self) -> bool:
        """Recupera el estado del LED desde la BD.

        La BD solo guarda el estado booleano (ON/OFF).
        El pin GPIO se obtiene exclusivamente de devices.yaml.

        Returns:
            state: True si encendido, False si apagado.
        """
        if not self._conn:
            return False
        cursor = await self._conn.execute(
            "SELECT state FROM led_state WHERE id = 1"
        )
        row = await cursor.fetchone()
        if row is None:
            return False
        return bool(row[0])

    async def save_led(self, state: bool) -> None:
        """Guarda el estado del LED en la BD.

        Solo persiste el estado booleano. El pin GPIO NO se guarda
        en BD — la fuente unica de verdad del hardware es devices.yaml.

        Args:
            state: True si encendido.
        """
        if not self._conn:
            return
        await self._conn.execute(
            "UPDATE led_state SET state = ?, updated_at = ? WHERE id = 1",
            (1 if state else 0, datetime.now(UTC).isoformat()),
        )
        await self._conn.commit()

    # ── Button ─────────────────────────────────────────────────

    async def get_button_count(self) -> int:
        """Recupera el contador de pulsaciones desde la BD.

        Returns:
            Contador acumulado.
        """
        if not self._conn:
            return 0
        cursor = await self._conn.execute(
            "SELECT press_count FROM button_state WHERE id = 1"
        )
        row = await cursor.fetchone()
        if row is None:
            return 0
        return int(row[0])

    async def save_button_count(self, count: int) -> None:
        """Guarda el contador de pulsaciones en la BD.

        Args:
            count: Nuevo valor del contador.
        """
        if not self._conn:
            return
        await self._conn.execute(
            "UPDATE button_state SET press_count = ?, updated_at = ? WHERE id = 1",
            (count, datetime.now(UTC).isoformat()),
        )
        await self._conn.commit()

    # ── Display Settings ────────────────────────────────────────

    async def get_display_settings(self) -> dict[str, str]:
        """Recupera los ajustes visuales del display desde la BD.

        Returns:
            Dict con font_family y text_size (defaults si no hay fila).
        """
        if not self._conn:
            return {"font_family": "dejavu", "text_size": "medium"}
        cursor = await self._conn.execute(
            "SELECT font_family, text_size FROM display_settings WHERE id = 1"
        )
        row = await cursor.fetchone()
        if row is None:
            return {"font_family": "dejavu", "text_size": "medium"}
        return {"font_family": str(row[0]), "text_size": str(row[1])}

    async def save_display_settings(self, font_family: str, text_size: str) -> None:
        """Guarda los ajustes visuales del display en la BD.

        Args:
            font_family: 'dejavu' | 'liberation'.
            text_size: 'small' | 'medium' | 'large'.
        """
        if not self._conn:
            return
        await self._conn.execute(
            "UPDATE display_settings SET font_family = ?, text_size = ?, updated_at = ? WHERE id = 1",
            (font_family, text_size, datetime.now(UTC).isoformat()),
        )
        await self._conn.commit()

    # ── Security Settings ───────────────────────────────────────

    async def get_security_settings(self) -> dict[str, object]:
        """Recupera los ajustes de seguridad del panel web desde la BD.

        Returns:
            Dict con ``password_hash`` (str) y ``password_enabled`` (bool).
            Si no hay fila (o la BD no está inicializada), devuelve los
            defaults: hash de ``1234`` y el flag según ``settings.security_mode``.
        """
        if not self._conn:
            return self._default_security_settings()
        cursor = await self._conn.execute(
            "SELECT password_hash, password_enabled FROM security_settings WHERE id = 1"
        )
        row = await cursor.fetchone()
        if row is None:
            return self._default_security_settings()
        return {"password_hash": str(row[0]), "password_enabled": bool(row[1])}

    async def save_security_settings(self, password_hash: str, password_enabled: bool) -> None:
        """Guarda los ajustes de seguridad del panel web en la BD.

        Args:
            password_hash: Hash PBKDF2 de la contraseña del panel.
            password_enabled: Flag de contraseña activada/desactivada.
        """
        if not self._conn:
            return
        await self._conn.execute(
            "UPDATE security_settings SET password_hash = ?, password_enabled = ?, "
            "updated_at = ? WHERE id = 1",
            (password_hash, 1 if password_enabled else 0, datetime.now(UTC).isoformat()),
        )
        await self._conn.commit()

    @staticmethod
    def _default_security_settings() -> dict[str, object]:
        """Devuelve los defaults de seguridad (hash de ``1234`` + flag inicial)."""
        from backend.app.config import settings
        from backend.app.services.password_hash import DEFAULT_PASSWORD, hash_password

        return {
            "password_hash": hash_password(DEFAULT_PASSWORD),
            "password_enabled": settings.security_mode == "protected",
        }

    # ── Event Log ──────────────────────────────────────────────

    async def log_event(self, event_type: str, payload: str | None = None) -> None:
        """Registra un evento en el log historico.

        Args:
            event_type: Tipo de evento (ej. "led_on", "button_pressed").
            payload: Datos adicionales en formato JSON string.
        """
        if not self._conn:
            return
        await self._conn.execute(
            "INSERT INTO event_log (timestamp, event_type, payload) VALUES (?, ?, ?)",
            (datetime.now(UTC).isoformat(), event_type, payload),
        )
        await self._conn.commit()
        await self._rotate_event_log()

    async def _rotate_event_log(self) -> None:
        """Elimina eventos antiguos si se excede MAX_EVENT_LOG_ROWS."""
        if not self._conn:
            return
        cursor = await self._conn.execute("SELECT COUNT(*) FROM event_log")
        row = await cursor.fetchone()
        if row and row[0] > self.MAX_EVENT_LOG_ROWS:
            excess = row[0] - self.MAX_EVENT_LOG_ROWS + 1000  # Borrar en bloques
            await self._conn.execute(
                "DELETE FROM event_log WHERE id IN ("
                "SELECT id FROM event_log ORDER BY id ASC LIMIT ?"
                ")",
                (excess,),
            )
            await self._conn.commit()
            logger.info("Rotacion event_log: %d filas eliminadas", excess)

    async def get_recent_events(self, limit: int = 50) -> list[dict[str, str | None]]:
        """Recupera los eventos mas recientes.

        Args:
            limit: Maximo de eventos a devolver.

        Returns:
            Lista de dicts con timestamp, event_type y payload.
        """
        if not self._conn:
            return []
        cursor = await self._conn.execute(
            "SELECT timestamp, event_type, payload FROM event_log "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [
            {"timestamp": row[0], "event_type": row[1], "payload": row[2]}
            for row in rows
        ]

    # ── Health ─────────────────────────────────────────────────

    async def is_healthy(self) -> bool:
        """Verifica que la BD responde correctamente.

        Returns:
            True si SELECT 1 funciona.
        """
        try:
            if not self._conn:
                return False
            await self._conn.execute("SELECT 1")
            return True
        except Exception:
            return False


# ── Singleton ──────────────────────────────────────────────────

_db: Persistence | None = None


async def get_persistence(db_path: str) -> Persistence:
    """Obtiene o crea la instancia singleton de Persistence.

    Args:
        db_path: Ruta al archivo SQLite.

    Returns:
        Instancia inicializada de Persistence.
    """
    global _db
    if _db is None:
        _db = Persistence(db_path)
        await _db.init()
    return _db


async def close_persistence() -> None:
    """Cierra la conexion de persistencia (para shutdown)."""
    global _db
    if _db:
        await _db.close()
        _db = None
