# FASE 8 · F3 — Security fail-closed en arranque (refactor 0.4.0)

Estado de partida: rama `main`, commit `ffa8e7b`, versión `0.3.4` (objetivo `0.4.0`).
Trabajo aislado solo de backend (seguridad) y sus tests; sin cambios en frontend ni display.

## Resumen

La auditoría reportó un **security fail-open**: si SQLite no estaba disponible durante
el arranque, el backend continuaba (solo `logger.warning`) y `SecurityManager.load()`
se tragaba el error dejando `enabled=False`. Un sistema previamente protegido arrancaba
así **DESPROTEGIDO**.

Se corrige con la solución mínima recomendada por la auditoría:

- SQLite es un componente **esencial**: si `get_persistence` falla, el `lifespan`
  registra `logger.critical(...)` y **relanza** la excepción. El backend no entra en
  READY y `systemd` reinicia el servicio.
- `SecurityManager.load()` ahora **falla cerrado**: no captura errores de lectura de
  `get_security_settings` ni de estructura de los datos (`KeyError`/`TypeError`), de
  modo que cualquier fallo de persistencia se propaga en vez de dejar el estado
  desprotegido.

## Archivos modificados

1. `backend/app/main.py` — bloque "Inicializar persistencia SQLite" (~líneas 164-183):
   - Sustituido `except Exception: logger.warning(...)` por
     `except Exception: logger.critical(...)` con mensaje explícito (SQLite esencial,
     backend no entra en READY, systemd debe reiniciar) y `raise` para relanzar.
   - Añadido comentario explicando el porqué: evitar arrancar desprotegido por
     fail-open del SecurityManager.
   - El resto del bloque (`get_persistence`, `set_persistence`, `restore_from_db`,
     `security_manager.load`) no se tocó.

2. `backend/app/services/security_manager.py` — método `load()` (~líneas 86-109):
   - Eliminados los dos `try/except` que hacían `return` dejando `_enabled=False`.
   - `data = await persistence.get_security_settings()` sin capturar (los errores de
     BD se propagan).
   - `password_hash = data["password_hash"]` y `password_enabled = bool(data["password_enabled"])`
     sin capturar (KeyError/TypeError se propagan = fail-closed).
   - Se mantienen el `with self._lock:` y el `logger.info` final.
   - Actualizado el docstring de `load()` para documentar el comportamiento fail-closed
     (nueva sección "Comportamiento fail-closed" y `Raises`).
   - Añadida nota al docstring de la clase `SecurityManager` indicando que `load()`
     falla cerrado ante errores de lectura.
   - `is_enabled()`, `verify_password()`, `set_enabled()`, `set_password()`, `reset()`
     e `__init__` no se tocaron.

3. `backend/tests/test_security.py`:
   - Añadido `from unittest.mock import AsyncMock` al bloque de imports.
   - Añadida clase `TestSecurityManagerFailClosed` con
     `test_load_raises_when_persistence_read_fails` (verifica fail-closed con
     `side_effect=RuntimeError`).

4. `backend/tests/test_main_lifespan.py`:
   - Añadido `test_sqlite_failure_prevents_ready` en `TestLifespanStartup`: verifica
     que el lifespan relanza el error (no entra en READY) cuando `get_persistence`
     lanza excepción, modelando el patrón de `test_persistence_initialized_and_state_restored`.

No se modificaron `frontend/`, `display/`, `SECURITY_MODE`, `config.py`, ni
`restore_from_db`. No se tocó la ortografía "contrasena"→"contraseña".

## Resultado de verificación

- **pytest**: `python -m pytest backend/tests display/tests -q`
  → `393 passed, 9 skipped` (5 warnings preexistentes de corutina no esperada en
  `restore_from_db`, no relacionados con este cambio).
- **ruff**: `python -m ruff check backend display scripts --config backend/pyproject.toml`
  → `All checks passed!`
- **mypy**: `python -m mypy app --config-file pyproject.toml` (desde `backend/`)
  → `Success: no issues found in 31 source files`

## Decisiones

- `SecurityManager.load()` propaga las excepciones (fail-closed) en lugar de capturarlas,
  porque el `lifespan` ya se encarga de abortar el arranque con `logger.critical` + `raise`.
  Así el estado de seguridad nunca queda ambiguo ante un fallo de persistencia.
- El nuevo test de lifespan se escribió combinando `pytest.raises(RuntimeError)` dentro
  del mismo `with` de los `patch` (en lugar de un `with` anidado) para cumplir SIM117.
- La nota sobre `docs/SECURITY.md` se actualizará en la fase de drift documental, no aquí.

## Nota de drift documental

`docs/SECURITY.md` se actualizará en la fase de drift documental para reflejar el nuevo
comportamiento fail-closed de SQLite en arranque.

## TEXTO DE PASO

```
Fase 3 del refactor 0.4.0 completada (security fail-closed). Rama main,
commit base ffa8e7b, versión 0.3.4 -> objetivo 0.4.0. Solo backend (seguridad)
y sus tests.

Hecho en esta fase:
- backend/app/main.py: el bloque de persistencia SQLite ahora usa
  logger.critical(...) + raise (fail-closed); SQLite es esencial, el backend no
  entra en READY y systemd reinicia. Comentario explicando el porqué.
- backend/app/services/security_manager.py: load() ya no traga errores;
  get_security_settings y el acceso a data se hacen sin capturar (KeyError/TypeError
  se propagan). Docstrings de load() y de la clase actualizados (fail-closed).
- backend/tests/test_security.py: import AsyncMock + clase
  TestSecurityManagerFailClosed con test_load_raises_when_persistence_read_fails.
- backend/tests/test_main_lifespan.py: test_sqlite_failure_prevents_ready.

Verificación:
- pytest backend/tests display/tests: 393 passed, 9 skipped.
- ruff: All checks passed.
- mypy (desde backend/): Success, 31 source files.

Sin commit (queda pendiente para el orquestador). No se tocaron frontend/, display/,
SECURITY_MODE, config.py, restore_from_db, ni la ortografía "contrasena"->"contraseña".
docs/SECURITY.md se actualizará en la fase de drift documental.

Continuar con la siguiente fase del refactor a 0.4.0.
```
