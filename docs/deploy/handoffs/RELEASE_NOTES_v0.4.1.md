# v0.4.1 — Correcciones de auditoría externa (patch de seguridad)

## Resumen

Patch release que corrige los hallazgos de la **auditoría externa** sobre la
versión `0.4.0`. Dos correcciones de seguridad (una de atomicidad fail-closed y
una de aislamiento del endpoint administrativo) y una de consistencia documental.

## Cambios

- `fix(security)` — **Atomicidad fail-closed de `SecurityManager`**: `set_enabled()`
  y `set_password()` ahora persisten **primero en SQLite** y solo actualizan la
  cache en memoria tras un guardado correcto. Si el guardado falla, la RAM queda
  intacta y el error se propaga (evita fail-open en tiempo de ejecución).
- `fix(security)` — **`/admin/*` solo `X-API-Key`**: `require_admin_api_key_always`
  ya no acepta la cookie de sesión del panel web. Una contraseña HMI de bajo
  privilegio (p. ej. la de fábrica `1234`) ya no puede convertirse indirectamente
  en credencial administrativa (SSH exec / deploy remoto).
- `docs` — `README.md` actualizado con los conteos reales de tests (396 pytest + 27 vitest).

## Verificación

- `pytest backend/tests/ display/tests/`: **396 passed, 15 skipped**.
- `ruff`: `All checks passed!`.
- `mypy` (`backend/app/`): `Success: no issues found in 31 source files`.
- `vitest`: **27 passed (3 files)**.
- HIL real (Pi, previo a esta release): 5/5 originales + 6/6 extendidos.

## Notas

- `VERSION` = `0.4.1`, coherente con los fallbacks de `backend/app/_version.py`
  (`_FALLBACK`) y `display/app.py`, y con `SECURITY.md` / `ARCHITECTURE.md`.

## Documentación

- `docs/deploy/handoffs/FASE8_F7_CIERRE.md` — cierre de esta fase.
- `docs/SECURITY.md` — separación `/admin/*` (X-API-Key únicamente).
