"""Tests para el sistema de migraciones versionadas de SQLite.

Cubre el runner incremental de `Persistence.init()` y las migraciones
individuales `_migration_001` / `_migration_002`, incluyendo la
compatibilidad con bases de datos legacy (tablas preexistentes sin
`schema_version`).

Patrones usados (idem `test_persistence.py`):
- BD en memoria `":memory:"` o archivo temporal `tempfile.mkstemp(suffix=".db")`.
- Limpieza con `Path(...).unlink(missing_ok=True)` y cierre con `await db.close()`.
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import aiosqlite
import pytest

from backend.app.services.persistence import Persistence


class TestMigrationRunner:
    """Tests del runner incremental de migraciones en `Persistence.init()`."""

    @pytest.mark.asyncio
    async def test_init_applies_all_migrations_on_new_db(self):
        """En BD nueva, `init()` aplica todas las migraciones y deja version 4."""
        db = Persistence(":memory:")
        await db.init()
        try:
            assert await db.get_schema_version() == 4
        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_init_is_idempotent(self):
        """Llamar `init()` dos veces no lanza error y mantiene la version en 4."""
        db = Persistence(":memory:")
        await db.init()
        try:
            await db.init()
            assert await db.get_schema_version() == 4
        finally:
            await db.close()


class TestMigration001:
    """Tests de la migracion inicial (schema_inicial)."""

    @pytest.mark.asyncio
    async def test_creates_tables_and_default_rows(self):
        """`_migration_001` crea las 4 tablas y las filas iniciales por defecto."""
        db = Persistence(":memory:")
        await db.init()
        try:
            cursor = await db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
                "('led_state', 'button_state', 'event_log', 'display_settings')"
            )
            rows = await cursor.fetchall()
            table_names = {row["name"] for row in rows}
            assert table_names == {
                "led_state",
                "button_state",
                "event_log",
                "display_settings",
            }

            assert await db.get_led() is False
            assert await db.get_button_count() == 0
            assert await db.get_display_settings() == {
                "font_family": "dejavu",
                "text_size": "medium",
            }
        finally:
            await db.close()


class TestMigration002:
    """Tests de la migracion del indice (indice_event_log)."""

    @pytest.mark.asyncio
    async def test_creates_index(self):
        """`_migration_002` crea el indice `idx_event_log_timestamp`."""
        db = Persistence(":memory:")
        await db.init()
        try:
            cursor = await db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='idx_event_log_timestamp'"
            )
            rows = await cursor.fetchall()
            assert [row["name"] for row in rows] == ["idx_event_log_timestamp"]
        finally:
            await db.close()


class TestMigration004:
    """Tests de la migracion que fuerza password_enabled=0 (off por defecto)."""

    @pytest.mark.asyncio
    async def test_resets_password_enabled_to_zero(self):
        """`_migration_004` apaga la contraseña en instalaciones previas."""
        db = Persistence(":memory:")
        await db.init()
        try:
            # Simula una instalacion previa con la contraseña activada.
            await db._conn.execute(
                "UPDATE security_settings SET password_enabled = 1 WHERE id = 1"
            )
            await db._conn.commit()

            await db._migration_004()

            data = await db.get_security_settings()
            assert data["password_enabled"] is False
        finally:
            await db.close()


class TestLegacyDatabase:
    """Tests de compatibilidad con bases de datos legacy."""

    @pytest.mark.asyncio
    async def test_legacy_db_preserves_data_and_creates_missing_tables(self):
        """BD legacy (tablas originales sin `schema_version`) conserva datos y
        crea las tablas que faltan.

        `init()` detecta las tablas legacy y ejecuta las migraciones idempotentes:
        `_migration_001` usa `CREATE TABLE IF NOT EXISTS` + `INSERT OR IGNORE`,
        por lo que NO pierde la fila guardada y ademas crea `display_settings`
        (tabla posterior al esquema legacy de 3 tablas). La version final es 4.
        """
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            # Simula una BD creada por la version antigua: las tablas originales
            # (`led_state`, `button_state`, `event_log`) con una fila `state=1`,
            # pero SIN tabla `schema_version`.
            conn = sqlite3.connect(path)
            conn.executescript(
                """
                CREATE TABLE led_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    state INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                INSERT INTO led_state (id, state, updated_at)
                    VALUES (1, 1, datetime('now'));

                CREATE TABLE button_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    press_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                INSERT INTO button_state (id, press_count, updated_at)
                    VALUES (1, 0, datetime('now'));

                CREATE TABLE event_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT
                );
                """
            )
            conn.commit()
            conn.close()

            db = Persistence(path)
            await db.init()
            try:
                # (a) No pierde los datos guardados en la tabla legacy.
                assert await db.get_led() is True
                # (b) Crea la tabla `display_settings` que faltaba (regresion).
                assert await db.get_display_settings() == {
                    "font_family": "dejavu",
                    "text_size": "medium",
                }
                # (c) Version final 4 tras aplicar migraciones 001-004.
                assert await db.get_schema_version() == 4
            finally:
                await db.close()
        finally:
            Path(path).unlink(missing_ok=True)


class TestMigrationsDeclarations:
    """Tests estructurales sobre la lista `_MIGRATIONS`."""

    def test_versions_strictly_increasing_and_unique(self):
        """Las versiones de `_MIGRATIONS` son unicas y estrictamente crecientes."""
        versions = [version for version, _name, _method in Persistence._MIGRATIONS]
        assert versions == sorted(versions), "las versiones deben ser crecientes"
        assert len(versions) == len(set(versions)), "las versiones deben ser unicas"

    def test_migration_names_reference_existing_methods(self):
        """Cada entrada apunta a un metodo real de `Persistence`."""
        for _version, _name, method_name in Persistence._MIGRATIONS:
            assert callable(getattr(Persistence, method_name, None))


class TestMigrationIdempotency:
    """Tests de idempotencia SQL de las migraciones individuales."""

    @pytest.mark.asyncio
    async def test_migrations_are_idempotent_at_sql_level(self):
        """`_migration_001` y `_migration_002` se pueden ejecutar dos veces sin error."""
        db = Persistence(":memory:")
        db._conn = await aiosqlite.connect(":memory:")
        try:
            await db._migration_001()
            await db._migration_001()
            await db._migration_002()
            await db._migration_002()

            cursor = await db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='idx_event_log_timestamp'"
            )
            rows = await cursor.fetchall()
            assert [row[0] for row in rows] == ["idx_event_log_timestamp"]
        finally:
            await db.close()
