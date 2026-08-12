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
from pathlib import Path
from datetime import datetime, timezone

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

        # Crear tablas si no existen
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS led_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state INTEGER NOT NULL DEFAULT 0,
                gpio_pin INTEGER NOT NULL DEFAULT 0,
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

            -- Insertar filas iniciales si no existen
            INSERT OR IGNORE INTO led_state (id, state, gpio_pin, updated_at)
                VALUES (1, 0, 0, datetime('now'));

            INSERT OR IGNORE INTO button_state (id, press_count, updated_at)
                VALUES (1, 0, datetime('now'));
        """)

        await self._conn.commit()
        logger.info("Persistencia inicializada: %s", self.db_path)

    async def close(self) -> None:
        """Cierra la conexion a la BD."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Persistencia cerrada")

    # ── LED ────────────────────────────────────────────────────

    async def get_led(self) -> tuple[bool, int]:
        """Recupera el estado del LED desde la BD.

        Returns:
            (state, gpio_pin): state es True si encendido, gpio_pin es el pin BCM.
        """
        if not self._conn:
            return False, 0
        cursor = await self._conn.execute(
            "SELECT state, gpio_pin FROM led_state WHERE id = 1"
        )
        row = await cursor.fetchone()
        if row is None:
            return False, 0
        return bool(row[0]), int(row[1])

    async def save_led(self, state: bool, gpio_pin: int) -> None:
        """Guarda el estado del LED en la BD.

        Args:
            state: True si encendido.
            gpio_pin: Numero de pin BCM.
        """
        if not self._conn:
            return
        await self._conn.execute(
            "UPDATE led_state SET state = ?, gpio_pin = ?, updated_at = ? WHERE id = 1",
            (1 if state else 0, gpio_pin, datetime.now(timezone.utc).isoformat()),
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
            (count, datetime.now(timezone.utc).isoformat()),
        )
        await self._conn.commit()

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
            (datetime.now(timezone.utc).isoformat(), event_type, payload),
        )
        await self._conn.commit()

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
