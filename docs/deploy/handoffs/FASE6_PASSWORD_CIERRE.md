# FASE 6 — Gestión de contraseña del panel web (activar/desactivar/cambiar) — CIERRE

- Rama/base: `main` @ `dacb880` (versión 0.3.2, working tree limpio al iniciar)
- Versión: 0.3.2 (NO se hizo bump; lo hará el orquestador)
- Resumen: implementada la contraseña de panel persistida en SQLite (hash PBKDF2,
  stdlib), separada de `ADMIN_API_KEY`. El flag runtime `security_manager.is_enabled()`
  reemplaza a `settings.security_mode` en login, protección de mutadores HMI y
  handshake WS. Nuevos endpoints `/api/auth/security` y `/api/auth/password`, y nuevo
  menú "Contraseña" en Configuración del panel web (SolidJS). Contraseña de fábrica
  por defecto `1234`. Sin commits git.

## Cambios

### CREADOS (6)

- `backend/app/services/password_hash.py` — hashing PBKDF2-HMAC-SHA256 con stdlib
  (`hashlib.pbkdf2_hmac` + `secrets`). `DEFAULT_PASSWORD = "1234"`,
  `hash_password()` y `verify_password()` (con `hmac.compare_digest`). Formato de
  almacén `pbkdf2_sha256$<iter>$<salt_b64>$<hash_b64>` (base64url), ~120 000
  iteraciones. Docstrings Google-style en español.
- `backend/app/services/security_manager.py` — singleton `SecurityManager` con
  `threading.Lock`. Estado inicial desde `settings.security_mode` + hash de `1234`.
  Métodos `is_enabled()`, `verify_password()`, `is_default_password()`,
  `async load(persistence)`, `async set_enabled()`, `async set_password()` y
  `reset()` (para tests; también resetea `_persistence`).
- `backend/app/models/security.py` — modelos Pydantic `SecurityStatus`,
  `SecurityToggleRequest` y `ChangePasswordRequest` (new con `min_length=4`).
- `backend/tests/test_security.py` — tests de `password_hash`, `security_manager`,
  persistencia y los endpoints `/api/auth/security` y `/api/auth/password` (16 tests).
- `frontend/src/components/SecuritySettings.tsx` — pantalla de configuración de
  contraseña: estado (activada/desactivada + si es la de fábrica), toggle, formulario
  "Cambiar contraseña" (actual + nueva + confirmar) con feedback de error, y `onBack`.
- `docs/deploy/handoffs/FASE6_PASSWORD_CIERRE.md` — este documento.

### MODIFICADOS (18)

- `backend/app/services/persistence.py` — nueva `_migration_003` (tabla
  `security_settings`: `password_hash`, `password_enabled`, `updated_at`; siembra con
  hash de `1234` y `password_enabled` según `settings.security_mode`). Métodos
  `get_security_settings()` y `save_security_settings()`.
- `backend/app/api/auth.py` — `LoginRequest.api_key` → `password` (min_length=1);
  login valida contra `security_manager.verify_password`; status usa
  `security_manager.is_enabled()`; nuevos `GET/POST /api/auth/security` y
  `POST /api/auth/password`; helper `_authorize_security_change`. Cambio de contraseña
  llama `session_manager.clear()`.
- `backend/app/api/deps.py` — `require_admin_api_key` usa
  `if not security_manager.is_enabled(): return None`; reordenado para comprobar la
  cookie de sesión ANTES del chequeo de `ADMIN_API_KEY` vacía.
  `require_admin_api_key_always` sin cambios.
- `backend/app/api/ws.py` — handshake usa `security_manager.is_enabled()` en lugar de
  `settings.security_mode`.
- `backend/app/main.py` — en `lifespan`, tras `get_persistence`, añadido
  `await security_manager.load(db)`.
- `backend/tests/conftest.py` — fixture `reset_security` (autouse) que llama
  `security_manager.reset()` antes de cada test.
- `backend/tests/test_auth.py` — fixtures/helpers migrados a `security_manager`;
  `_login` recibe `password`; añadidos tests de login con contraseña de panel y
  validación de password vacío (422).
- `backend/tests/test_hmi.py` — fixture `protected_mode` migrado a `security_manager`.
- `backend/tests/test_ws_endpoint.py` — fixture `protected_mode` migrado a
  `security_manager`.
- `backend/tests/test_migrations.py` — versión de esquema esperada a 3 (migración 003).
- `frontend/src/App.tsx` — tipo `View` con `"security"`; `goSecurity()`; prop
  `onSecurity` a `ConfigScreen`; render de `SecuritySettings`; `handleLogin` con
  `password` y mensaje "Contraseña incorrecta".
- `frontend/src/components/ConfigScreen.tsx` — botón "Contraseña" (icono candado) que
  llama `onSecurity`, manteniendo el estilo del resto de botones.
- `frontend/src/components/LoginScreen.tsx` — renombrados textos/labels de "clave de
  administración" a "contraseña"; prop `onLogin(apiKey)` → `onLogin(password)`.
- `frontend/src/hooks/useApi.ts` — `login(password)`; nuevos `getSecurity()`,
  `setSecurityEnabled(enabled, current?)` y `changePassword(current, new)`.
- `frontend/src/types/api.ts` — nueva interfaz `SecurityStatus` (`enabled`,
  `is_default`).
- `frontend/src/tests/components.test.tsx` — test de import del nuevo
  `@/components/SecuritySettings`.
- `docs/SECURITY.md` — nuevo modelo documentado: contraseña de panel persistida,
  default `1234`, endpoints `/api/auth/security` y `/api/auth/password`, y rol de
  `SECURITY_MODE`/`ADMIN_API_KEY` como valor inicial/M2M.
- `.env.example` — nota de que la contraseña de panel se gestiona desde la UI
  (default `1234`) y persiste en SQLite.

## Verificación

- **pytest backend** `python -m pytest backend/tests/ -q`:
  **305 passed / 7 skipped / 5 warnings** (107.06 s) — verde.
- **pytest display** `python -m pytest display/tests/ -q`:
  **64 passed / 2 skipped** (0.28 s) — verde.
  (Total: **369 passed / 9 skipped / 5 warnings**.)
- **ruff** `python -m ruff check backend/ display/ scripts/ --config backend/pyproject.toml`:
  **All checks passed!** — verde.
- **vitest** `npm run test` (frontend): **3 files / 27 tests passed** — verde.
- **build** `npm run build` (frontend): `tsc -b && vite build` correcto
  (103 modules, `dist/` generado) — verde.
- **git status --short**: sin artefactos (`__pycache__`/`.pyc`/`.pytest_cache`/
  `.ruff_cache`/`.mypy_cache`/`dist`/`node_modules`). Solo archivos de código/docs de
  esta fase.

## Decisiones

1. **Contraseña de panel separada de `ADMIN_API_KEY`.** La contraseña de panel se
   persiste en SQLite (hash PBKDF2 stdlib) y es el flag de runtime del login/panel;
   `ADMIN_API_KEY` sigue siendo la clave M2M (`X-API-Key`) y de `/admin/*`
   (`require_admin_api_key_always` no cambia). Coherente con el diseño del handoff.
2. **Hash PBKDF2 con stdlib, sin dependencias.** `hashlib.pbkdf2_hmac` + `secrets` +
   `hmac.compare_digest`, formato `pbkdf2_sha256$<iter>$<salt_b64>$<hash_b64>`
   (base64url) y ~120 000 iteraciones. Evita añadir paquetes (restricción absoluta).
3. **Reorden de `require_admin_api_key`.** La cookie de sesión válida se comprueba
   ANTES del chequeo de `ADMIN_API_KEY` vacía, para que el login por panel funcione
   aunque `ADMIN_API_KEY` esté vacío. El path `X-API-Key` sigue exigiendo
   `settings.admin_api_key`.
4. **`test_config.py` y `test_integration.py` NO se modificaron.** Aunque el handoff
   los señalaba como "afectados (verificar)", no dependían directamente de
   `settings.security_mode`; el nuevo fixture `reset_security` (autouse) en
   `conftest.py` cubre el estado entre tests sin tocarlos.
5. **`SecurityManager.reset()` resetea también `_persistence`.** Evita que el singleton
   retenga una conexión/DB entre tests (fugas de estado en la suite).
6. **Cambio de contraseña revoca sesiones.** `session_manager.clear()` en
   `POST /api/auth/password` fuerza re-login de todos los paneles.

## Pendientes / fuera de alcance

- **Bump de versión** (a `0.3.3` o el que decida el orquestador): fuera de alcance.
  No se tocó `VERSION`, `_version.py`, `pyproject.toml`, `package.json`,
  `package-lock.json` ni `display/app.py`.
- **Suite de gates completos** (mypy, bandit, pip-audit, npm audit) no ejecutados en
  esta fase: corresponden al cierre final del orquestador (gates globales de gobernanza).
- **Test de la UI de `SecuritySettings`** vía vitest: se cubrió como mínimo con el
  test de import del componente (export); no se añadieron tests de interacción DOM
  (el handoff lo marcaba "si son razonables").

## TEXTO DE PASO (pegar en el siguiente chat)

"Proyecto RPi HMI en `main` @ `dacb880` (working tree con Fase 6, sin commit).
Fase 6 (contraseña del panel web) completada: contraseña de panel persistida en
SQLite (hash PBKDF2 stdlib, default `1234`) separada de `ADMIN_API_KEY`; nuevo
singleton `SecurityManager` (flag runtime `is_enabled()` que reemplaza a
`settings.security_mode` en `deps.py`, `ws.py` y `auth.py/status`); nuevos endpoints
`GET/POST /api/auth/security` y `POST /api/auth/password` (cambio de contraseña
revoca sesiones); `require_admin_api_key_always` sin cambios; nuevo menú 'Contraseña'
en Configuración (SolidJS, componente `SecuritySettings`). Verificación: pytest
369 passed / 9 skipped (305 backend + 64 display) · ruff 'All checks passed!' ·
vitest 27 passed · build verde · git sin artefactos. Pendientes: bump de versión y
gates globales (mypy, bandit, pip-audit, npm audit) quedan para el orquestador.
Lee `docs/deploy/handoffs/FASE6_PASSWORD_CIERRE.md`."
