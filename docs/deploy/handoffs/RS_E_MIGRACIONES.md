# Handoff RS_E — Tests de migraciones versionadas de SQLite

## Resultado
Completado. Se añadió una suite dedicada al sistema de migraciones versionadas
de `backend/app/services/persistence.py`, que hasta ahora no tenía tests propios
(solo `test_persistence.py` cubría CRUD/rotación/health).

## Tests añadidos (8 en total)

Archivo: `backend/tests/test_migrations.py` (nuevo)

- `TestMigrationRunner`
  - `test_init_applies_all_migrations_on_new_db` — en BD nueva, `init()` deja `schema_version == 2`.
  - `test_init_is_idempotent` — `init()` dos veces no lanza error y mantiene versión 2.
- `TestMigration001`
  - `test_creates_tables_and_default_rows` — crea `led_state`, `button_state`, `event_log`, `display_settings` y filas iniciales (`get_led() is False`, `get_button_count() == 0`, `get_display_settings() == {"font_family":"dejavu","text_size":"medium"}`).
- `TestMigration002`
  - `test_creates_index` — verifica en `sqlite_master` que existe `idx_event_log_timestamp`.
- `TestLegacyDatabase`
  - `test_legacy_db_preserves_data_and_marks_version_1` — BD legacy con tablas originales sin `schema_version`: no pierde datos (`get_led() is True`) y no re-crea el esquema.
- `TestMigrationsDeclarations`
  - `test_versions_strictly_increasing_and_unique` — versiones de `_MIGRATIONS` estrictamente crecientes y únicas.
  - `test_migration_names_reference_existing_methods` — cada entrada apunta a un método real.
- `TestMigrationIdempotency`
  - `test_migrations_are_idempotent_at_sql_level` — `_migration_001`/`_migration_002` ejecutables dos veces sin error (guardas `IF NOT EXISTS`).

## Archivos
- `backend/tests/test_migrations.py` — [nuevo] suite de 8 tests.
- `docs/deploy/handoffs/RS_E_MIGRACIONES.md` — [nuevo] este handoff.
- No se modificó `backend/app/services/persistence.py` ni ningún otro archivo.

## Verificación ejecutada (gate)

Desde la raíz del repo:

1. `python -m pytest backend/tests/test_migrations.py -q`

```
============================= test session starts =============================
platform win32 -- Python 3.13.7, pytest-8.4.2, pluggy-1.6.0
rootdir: E:\SINCRONIZADO\Informatica\Proyectos VisualStudio\Python\Rapsberry\Rpi_Pantalla_V1\backend
configfile: pyproject.toml
plugins: anyio-4.12.1, asyncio-1.4.0, cov-7.0.0, mock-3.15.1, qt-4.5.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 8 items

backend\tests\test_migrations.py ........                                [100%]

============================== 8 passed in 0.10s ==============================
```

2. `python -m ruff check backend/`

```
All checks passed!
```

## Riesgos / hallazgos

- **RIESGO (comportamiento real del runner legacy, distinto del enunciado):**
  en una BD legacy, `init()` NO se detiene en la versión 1. Tras marcar
  `schema_version=1`, el bucle de migraciones continúa y aplica
  `_migration_002` (índice), por lo que la **versión final observable es 2**,
  no 1. El test refleja este comportamiento real (`get_schema_version() == 2`)
  y documenta que la "marca de versión 1" es un estado intermedio interno.

- **RIESGO (bug latente potencial):** `_migration_002` ejecuta
  `CREATE INDEX ... ON event_log (timestamp)`. Si una BD legacy solo tuviera
  `led_state`/`button_state` pero NO `event_log`, `init()` lanzaría
  `sqlite3.OperationalError: no such table: main.event_log`. El test legacy
  usa el esquema original completo (3 tablas) documentado en
  `docs/audits/fase6-persistencia.md`, por lo que es coherente con la realidad;
  pero conviene validar el caso "legacy sin `event_log`" si alguna instalación
  antigua llegó a ese estado.

- **Acoplamiento a privados en tests:** los tests de migración acceden a
  `db._conn` y a `_migration_001`/`_migration_002` (igual que ya hace
  `test_persistence.py` con `db._conn`). Es aceptable para tests unitarios,
  pero implica que cambios internos de `Persistence` pueden romperlos.

- **Idempotencia de `init()` con la misma instancia:** `init()` no cierra la
  conexión existente, por lo que re-invocarlo sobre la misma instancia es
  seguro. No se probó `init()` sobre instancias distintas apuntando al mismo
  archivo (abriría una segunda conexión WAL); si se requiere, añadir un test
  dedicado.

## Texto de paso al siguiente agente
Migraciones de SQLite cubiertas con 8 tests nuevos en
`backend/tests/test_migrations.py`; gate verde (`8 passed`, ruff limpio). Hallazgo
a revisar: el runner legacy finaliza en versión 2 (no 1) porque `_migration_002`
también se aplica, y podría romper si una BD legacy carece de `event_log`.

## Seguimiento del hilo principal (post-Fase 1)

El bug latente señalado en "Riesgos / hallazgos" fue corregido por el hilo
principal en `backend/app/services/persistence.py`: la rama legacy ya NO marca
`schema_version=1` a mano; ahora las migraciones idempotentes (`_migration_001`
con `CREATE TABLE IF NOT EXISTS` + `INSERT OR IGNORE`) se ejecutan igualmente,
creando las tablas que falten (`display_settings`) sin perder datos.

El test legacy se renombró a
`test_legacy_db_preserves_data_and_creates_missing_tables` y ahora además
verifica que `get_display_settings()` devuelve los defaults (regresión del bug).
Gate re-verificado por el hilo principal: `pytest backend/tests/` 268 passed /
7 skipped, `ruff` y `mypy` limpios.
