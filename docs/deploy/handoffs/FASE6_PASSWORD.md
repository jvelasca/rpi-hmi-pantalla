# FASE 6 — Gestión de contraseña del panel web (activar/desactivar/cambiar) — ENTRADA

- Rama/base: `main` @ `dacb880` (versión 0.3.2, working tree limpio)
- Objetivo: añadir un menú en "Configuración" que permita **activar/desactivar** la
  contraseña del panel web y **cambiarla**. La **contraseña de fábrica por defecto
  será `1234`**.
- Alcance: backend (auth/seguridad + persistencia), frontend (nuevo menú), tests y docs.
  NO incluye el bump de versión (lo hará el orquestador después).

## Reglas de gobernanza (OBLIGATORIAS)
- Lee `docs/PREMISAS_ESENCIALES.md`. Todo cambio lleva docstring (Google-style en
  español) y test. Documenta en `docs/SECURITY.md` y `.env.example` si aplica.
- No commits git (los hará el orquestador).
- No toques el versionado (`VERSION`, `_version.py`, `pyproject.toml`,
  `package.json`, `display/app.py`).

## Diseño acordado (respétalo)

Introducir una **contraseña de panel persistida** en SQLite, separada de
`ADMIN_API_KEY` (que sigue siendo la clave M2M de `X-API-Key` y de `/admin/*`).
El estado de "contraseña activada/desactivada" pasa a ser el **flag de runtime** que
controla el login del panel y la protección de los mutadores HMI (equivale al actual
`SECURITY_MODE` local/protected, pero cambiable en caliente y persistido).

### 1. Hashing de contraseña (stdlib, sin dependencias)
Crear `backend/app/services/password_hash.py`:
- `DEFAULT_PASSWORD = "1234"`.
- `hash_password(password: str) -> str` — PBKDF2-HMAC-SHA256 con salt aleatorio
  (`hashlib.pbkdf2_hmac` + `secrets`). Formato de almacen: `pbkdf2_sha256$<iter>$$<salt_b64>$$<hash_b64>` (base64url).
- `verify_password(password: str, stored: str) -> bool` — `hmac.compare_digest`.
- Usa ~120_000 iteraciones (ajustable). No dependencias nuevas.

### 2. Persistencia (`backend/app/services/persistence.py`)
- Nueva migración `_migration_003` (añadir a `_MIGRATIONS`): crea tabla
  `security_settings` (id=1): `password_hash TEXT NOT NULL`, `password_enabled
  INTEGER NOT NULL DEFAULT 1`, `updated_at TEXT NOT NULL`.
  - `INSERT OR IGNORE ... VALUES (1, <hash de "1234">, <1 si settings.security_mode
    == "protected" else 0>, datetime('now'))`.
  - Importa `settings` y `password_hash` para sembrar la fila inicial (cuidado con
    imports circulares: usa import dentro del método si hace falta).
- Métodos nuevos:
  - `async get_security_settings() -> dict` (`{"password_hash": str, "password_enabled": bool}`; defaults si no hay fila).
  - `async save_security_settings(password_hash: str, password_enabled: bool) -> None`.

### 3. SecurityManager (`backend/app/services/security_manager.py`, singleton)
- Cache en memoria con `threading.Lock` (los checks de deps/ws son síncronos).
- Estado inicial (antes de `load`): `_enabled = (settings.security_mode == "protected")`,
  `_password_hash = hash_password(DEFAULT_PASSWORD)`.
- Métodos:
  - `is_enabled() -> bool` (síncrono).
  - `verify_password(plain: str) -> bool` (síncrono).
  - `is_default_password() -> bool` (síncrono, `verify_password("1234", ...)`).
  - `async load(persistence)` — lee de BD y actualiza cache (llamado en lifespan).
  - `async set_enabled(enabled: bool)` — persiste + cache.
  - `async set_password(new: str)` — persiste + cache.
  - `reset()` — para tests (devuelve a defaults).

### 4. Modelos (`backend/app/models/security.py`, nuevo)
- `SecurityStatus(BaseModel)`: `enabled: bool`, `is_default: bool`.
- `SecurityToggleRequest(BaseModel)`: `enabled: bool`, `current: str | None = None`.
- `ChangePasswordRequest(BaseModel)`: `current: str`, `new: str = Field(min_length=4)`.
- `LoginRequest` (en `auth.py`): renombrar campo `api_key` → `password` (min_length=1).

### 5. Endpoints (`backend/app/api/auth.py`)
- **Login** `POST /api/auth/login`: validar `body.password` contra
  `security_manager.verify_password` (no contra `settings.admin_api_key`). Mantener
  rate-limit y emisión de cookie. `_signing_key()` puede seguir igual (basada en
  boot secret + ADMIN_API_KEY); no es crítico.
- **Status** `GET /api/auth/status`: `security_mode` = `"protected"` si
  `security_manager.is_enabled()` else `"local"`; `authenticated` = (not enabled)
  or sesión válida.
- **NUEVO** `GET /api/auth/security` → `SecurityStatus` (público).
- **NUEVO** `POST /api/auth/security` body `SecurityToggleRequest` → `SecurityStatus`.
  Autorización (helper `_authorize_security_change(request, current)`): permitir si
  (a) cookie de sesión válida, (b) `X-API-Key` coincide con `settings.admin_api_key`
  (si configurada), o (c) `current` verifica contra la contraseña almacenada.
  Si no, 401. Aplica rate-limit sobre fallos. Persiste con `security_manager.set_enabled`.
- **NUEVO** `POST /api/auth/password` body `ChangePasswordRequest` → `{"success": true}`.
  Requiere que `current` verifique (siempre). Al éxito: `security_manager.set_password(new)`
  y `session_manager.clear()` (forzar re-login). Aplica rate-limit. Si `current` no
  verifica → 401.
- Helper `_client_ip` ya existe; reutilizarlo.

### 6. `backend/app/api/deps.py`
- `require_admin_api_key`: sustituir `if settings.security_mode == "local": return None`
  por `if not security_manager.is_enabled(): return None`. REORDENAR para que la
  sesión válida se compruebe ANTES del chequeo de `ADMIN_API_KEY` vacía (la cookie del
  panel debe funcionar aunque `ADMIN_API_KEY` esté vacía). El path `X-API-Key` sigue
  exigiendo `settings.admin_api_key`.
- `require_admin_api_key_always` (para `/admin/*`): NO cambia (sigue con
  `settings.admin_api_key` y sesión).

### 7. `backend/app/api/ws.py`
- Sustituir `if settings.security_mode == "protected":` por
  `if security_manager.is_enabled():`. El resto (loopback, sesión, X-API-Key) igual.

### 8. `backend/app/main.py` (lifespan)
- Tras `db = await get_persistence(...)`, añadir `await security_manager.load(db)`.

### 9. Frontend (SolidJS, mantener tema oscuro existente)
- `frontend/src/hooks/useApi.ts`:
  - `login(password)` (renombrar param; mismo endpoint `/auth/login` con body `{password}`).
  - `getSecurity()` → `GET /auth/security`.
  - `setSecurityEnabled(enabled, current?)` → `POST /auth/security`.
  - `changePassword(current, new)` → `POST /auth/password`.
- `frontend/src/App.tsx`:
  - Añadir `"security"` al tipo `View`.
  - `goSecurity()` → `setView("security")` (SIN `commandDisplay`).
  - Pasar `onSecurity={goSecurity}` a `ConfigScreen`.
- `frontend/src/components/ConfigScreen.tsx`: añadir botón "Contraseña" (icono de
  candado) que llame `onSecurity`. Mantener estilo de los demás botones.
- **NUEVO** `frontend/src/components/SecuritySettings.tsx`:
  - Muestra estado actual (activada/desactivada + si es la de fábrica).
  - Toggle activar/desactivar (usa `setSecurityEnabled`).
  - Formulario "Cambiar contraseña" (actual + nueva + confirmar) con feedback de error.
  - `onBack` para volver a Configuración.
- `frontend/src/components/LoginScreen.tsx`: renombrar textos/labels de
  "clave de administración" a "contraseña"; el input ya es `type=password`. Renombrar
  prop `onLogin(apiKey)` → `onLogin(password)`.

### 10. Tests
- **Nuevo** `backend/tests/test_security.py`:
  - login con "1234" (default) funciona cuando `password_enabled=true`.
  - `GET /auth/security` refleja enabled/is_default.
  - cambiar contraseña: login vieja falla, nueva funciona; sesiones revocadas.
  - activar/desactivar: `auth/status` y `require_admin_api_key` lo reflejan.
  - endpoints de security exigen autorización (401 sin credenciales).
  - round-trip de persistencia (guardar/cargar).
- **Actualizar** los tests que dependen de `settings.security_mode` para que
  sembren `security_manager` (usar `security_manager.reset()`/`set_enabled` en
  fixtures, o un fixture en `conftest.py`). Afectados (verificar): `test_auth.py`,
  `test_hmi.py`, `test_ws_endpoint.py`, `test_config.py`, `test_integration.py`.
- **Frontend**: tests de `SecuritySettings` (vitest) si son razonables; como mínimo
  que `npm run test` siga verde y `npm run build` compile.

### 11. Docs
- `docs/SECURITY.md`: documentar el nuevo modelo (contraseña de panel persistida,
  default `1234`, endpoints `/api/auth/security` y `/api/auth/password`, y que
  `SECURITY_MODE`/`ADMIN_API_KEY` pasan a ser el valor inicial/M2M).
- `.env.example`: nota de que la contraseña de panel es gestionable desde la UI
  (default `1234`) y persiste en SQLite.

## NO tocar (fuera de alcance)
`VERSION`, `_version.py`, `pyproject.toml` (raíz y backend), `package.json`,
`package-lock.json`, `display/app.py`, `config/systemd/`, `config/sudoers.d/`,
`backend/config/devices.yaml`, `.github/`.

## Verificación final (ejecutar y reportar números reales)
1. `python -m pytest backend/tests/ display/tests/ -q` — verde.
2. `ruff check backend/ display/ scripts/ --config backend/pyproject.toml` — verde.
3. `cd frontend && npm run test` y `npm run build` — verdes.
4. `git status --short` sin artefactos.

## Entregable
Escribe `docs/deploy/handoffs/FASE6_PASSWORD.md` (entrada) y
`docs/deploy/handoffs/FASE6_PASSWORD_CIERRE.md` (cierre) con: resumen factual,
lista exacta de archivos, resultados de verificación, decisiones, y "TEXTO DE PASO".

Devuélveme: (1) resumen, (2) archivos tocados, (3) resultados pytest/ruff/vitest/build,
(4) decisiones y pendientes.
