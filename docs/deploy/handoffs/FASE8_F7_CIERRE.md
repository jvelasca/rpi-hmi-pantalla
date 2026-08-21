# FASE 8 / F7 — Correcciones de auditoría externa + bump a 0.4.1 — CIERRE

Estado de partida: rama `main`, commit `1d39a05`, versión `0.4.0` (release v0.4.0
publicada). Tras la auditoría externa se aplicaron dos correcciones de seguridad
y una de documentación, y se eleva la versión a `0.4.1`.

## Cambios

### Correcciones de seguridad (auditoría externa)

1. `backend/app/services/security_manager.py` — `set_enabled()` y `set_password()`
   persisten **primero en SQLite** y solo actualizan la cache en memoria tras un
   guardado correcto (fail-closed). Antes actualizaban RAM antes de persistir, lo
   que podía dejar el proceso desprotegido (fail-open) si `save_security_settings`
   fallaba.
2. `backend/app/api/deps.py` — `require_admin_api_key_always` deja de aceptar la
   cookie de sesión del panel web. `/admin/*` exige **solo** `X-API-Key`
   (ADMIN_API_KEY), de modo que una contraseña HMI de bajo privilegio no puede
   conceder acceso administrativo (SSH/deploy). Se elimina el parámetro `request`.
3. `docs/SECURITY.md` — tabla de clasificación y dependencias de auth actualizadas:
   `/admin/*` = `X-API-Key` únicamente (ya no "o cookie de sesión").

### Tests nuevos/actualizados

4. `backend/tests/test_security.py` — `TestSecurityManagerSetFailClosed` con 2 tests
   (`test_set_enabled_keeps_ram_on_persistence_failure`,
   `test_set_password_keeps_ram_on_persistence_failure`).
5. `backend/tests/test_integration.py` — `test_admin_does_not_accept_hmi_session_cookie`
   (cookie HMI → 401 en `/admin/deploy/scan`; `X-API-Key` → 200).
6. `backend/tests/test_config.py` — ajustado `test_require_admin_api_key_always_503_without_key`
   a la nueva firma (sin `request`).

### Documentación / consistencia

7. `README.md` — conteos reales: 396 pytest + 27 vitest (antes 346 + 26).
8. Bump de versión 0.4.0 → 0.4.1 en: `VERSION`, `pyproject.toml`,
   `backend/pyproject.toml`, `backend/app/_version.py` (`_FALLBACK`),
   `display/app.py` (fallback `_load_version`), `frontend/package.json` y
   `frontend/package-lock.json` (2 apariciones raíz, sin tocar dependencias).
9. Docs "actuales" a 0.4.1: `docs/ARCHITECTURE.md` (título + árbol VERSION),
   `docs/SECURITY.md` (línea 7), `docs/CONTEXT.md` (Branch/versión, sección
   "Ultima sesion", fila Tests) y `docs/PREMISAS_ESENCIALES.md` (línea 6 +
   sección 9 marca F0-F7 completadas).
10. Nuevos: `docs/deploy/handoffs/FASE8_F7_CIERRE.md` (este documento) y
    `docs/deploy/handoffs/RELEASE_NOTES_v0.4.1.md`.

## Verificación

- **pytest**: `python -m pytest backend/tests/ display/tests/ -q`
  → `396 passed, 15 skipped` (5 warnings preexistentes de corutina no esperada en
  `restore_from_db`, no relacionados).
- **ruff**: `python -m ruff check backend/ display/ scripts/ --config backend/pyproject.toml`
  → `All checks passed!`
- **mypy**: `python -m mypy app/ --config-file pyproject.toml` (desde `backend/`)
  → `Success: no issues found in 31 source files`
- **vitest**: `npm run test` (desde `frontend/`) → `27 passed (3 files)`.

## Nota sobre la observación de "VERSION 0.3.4"

La auditoría externa reportó que `VERSION` contenía `0.3.4`. Verificado contra el
árbol y contra HEAD: `VERSION` **ya era `0.4.0`** antes de esta fase (`git grep
"0\.3\.4"` en ficheros de versión no devolvía coincidencias). No hubo drift real;
se dejó como estaba y ahora pasa a `0.4.1`.

## Decisiones

- **Patch release (0.4.1)** en lugar de re-etiquetar `v0.4.0`: la release v0.4.0 ya
  estaba publicada; las correcciones post-auditoría se publican como parche semver.
- No se aborda la limpieza opcional del "modo sin BD" del health check (P2 no
  bloqueante, señalado por la auditoría como "Opcional"). Queda pendiente/opcional.

## Pendientes / fuera de alcance

- Limpieza opcional: `_check_db()` de `/health` conserva el fallback "modo sin BD"
  legacy (conceptualmente muerto tras declarar SQLite esencial). No operativo; P2.
- Pruebas destructivas manuales (apagado brusco físico, corrupción de SQLite viva)
  siguen documentadas en `docs/deploy/handoffs/HIL_0.4.0_RUNBOOK.md` §4.

## TEXTO DE PASO (pegar en el siguiente chat)

```
Fase 8 / F7 completada: correcciones de auditoría externa + bump a 0.4.1.
Rama main, base 1d39a05 (v0.4.0) -> 0.4.1 (release patch).

Hecho:
- SecurityManager.set_enabled()/set_password() ahora persisten SQLite ANTES de RAM
  (fail-closed; evita fail-open si el guardado falla).
- /admin/* (require_admin_api_key_always) solo acepta X-API-Key; ya no acepta cookie
  de sesión HMI (una contraseña de panel de bajo privilegio no da acceso admin).
- README actualizado a conteos reales (396 pytest + 27 vitest).
- Bump 0.4.0 -> 0.4.1 en VERSION, pyproject (x2), _version.py, display/app.py,
  frontend/package.json + package-lock.json, y docs actuales (ARCHITECTURE, SECURITY,
  CONTEXT, PREMISAS_ESENCIALES).
- Nuevos: FASE8_F7_CIERRE.md y RELEASE_NOTES_v0.4.1.md.

Verificación:
- pytest: 396 passed, 15 skipped. ruff: All checks passed.
- mypy (backend/app): 31 source files OK. vitest: 27 passed.

Nota: la observación "VERSION=0.3.4" era incorrecta; VERSION ya era 0.4.0.

Pendiente opcional: limpieza del "modo sin BD" legacy del health check (P2).
```
