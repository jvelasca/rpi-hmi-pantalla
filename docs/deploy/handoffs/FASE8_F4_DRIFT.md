# FASE 8 · F4 — Eliminación de `SECURITY_MODE` + corrección de contrato de login (refactor 0.4.0)

Estado de partida: rama `main`, commit `901d21b`, versión `0.3.4` (objetivo `0.4.0`).
Trabajo aislado y metódico. Sin commit (queda pendiente para el orquestador).

## Resumen

Se elimina por completo el concepto legacy `SECURITY_MODE`/`security_mode`
(`local`/`protected`), que ya no gobierna la protección. El estado real de la
protección es `security_manager.is_enabled()`, persistido en SQLite
(`password_enabled`) y leído por `security_manager.load()`. Además se corrige el
contrato de login documentado: `{"api_key": "..."}` → `{"password": "..."}` y
"clave" (referida a la contraseña del panel) → "contraseña del panel".

El contrato de `GET /api/auth/status` cambia: el campo `security_mode` (string
`"local" | "protected"`) pasa a ser **`security_enabled`** (booleano). Esto
arrastra al frontend (`AuthStatus` en `useApi.ts` y el signal de `App.tsx`).

## Archivos modificados

### Código y configuración

1. `backend/app/config.py`
   - Eliminado el campo `security_mode` (`Literal["local", "protected"]`).
   - Eliminada su mención en el docstring de variables de entorno (`SECURITY_MODE: ...`).
   - Eliminada la rama de `model_post_init` que validaba `security_mode == "protected"`.
     Se conservan las ramas de `enable_admin_api` y `admin_api_key`.

2. `.env.example`
   - Eliminados `SECURITY_MODE=local` y el bloque "Modo de seguridad".
   - Sustituido el comentario "SECURITY_MODE solo fija su estado inicial" por una
     nota: la protección se activa desde el panel (cambiando primero `1234`).

3. `backend/app/api/deps.py`
   - Docstring del módulo: descrito el mecanismo real (`security_manager.is_enabled()`,
     "desactivada por defecto hasta activarla en el panel"). Sin menciones a
     `SECURITY_MODE`/`local`/`protected`.
   - Docstrings de `require_admin_api_key` y `require_admin_api_key_always`
     actualizados; comentario de `_LOOPBACK_HOSTS` sin "modo protected".

4. `backend/app/api/network.py`
   - Docstrings que citaban `SECURITY_MODE=protected` → "cuando la contraseña del
     panel está activada (`require_admin_api_key`)".

5. `backend/app/api/auth.py`
   - `GET /api/auth/status` (`auth_status`): el campo de respuesta pasa de
     `security_mode` a **`security_enabled`** (booleano).
     `{"security_enabled": enabled, "authenticated": (not enabled) or session_manager.is_valid(token)}`.
     Docstring actualizado.

6. `backend/app/services/security_manager.py`
   - Docstring del módulo: el estado real es `password_enabled` persistido en SQLite,
     leído por `security_manager.load()` (sin `SECURITY_MODE`).

7. `backend/app/services/persistence.py`
   - Docstring de `_migration_003`: mismo cambio de redacción (sin `SECURITY_MODE`).

### Frontend

8. `frontend/src/hooks/useApi.ts` — interfaz `AuthStatus`: `security_mode: "local" | "protected"` → `security_enabled: boolean`.
9. `frontend/src/App.tsx` — signal `securityMode` (`"local" | "protected" | null`) → `securityEnabled` (`boolean | null`); actualizados `onMount`, `createEffect` de 401, `handleLogin` y `needsLogin` (`securityEnabled() && !authenticated()`).
10. `frontend/src/hooks/useWebSocket.ts` — comentario `SECURITY_MODE=protected` → "Cuando la contraseña del panel está activada".
11. `frontend/.env.example` — comentario de autenticación actualizado (sin `SECURITY_MODE`; login con la contraseña del panel, no con `ADMIN_API_KEY`).

### Tests (backend)

12. `backend/tests/test_security.py` — fixture `protected_mode` sin monkeypatch de `security_mode`; aserciones `status["security_enabled"] is True` / `is False`.
13. `backend/tests/test_auth.py` — sin monkeypatch de `security_mode` (fixture y `test_login_works_without_admin_key`, que ahora usa `asyncio.run(security_manager.set_enabled(True))`); aserción `security_enabled` is True; docstring del módulo sin `SECURITY_MODE`.
14. `backend/tests/test_hmi.py` — fixture sin monkeypatch de `security_mode`; docstrings (módulo y clase) actualizados.
15. `backend/tests/test_ws_endpoint.py` — fixture sin monkeypatch de `security_mode`; comentario de sección y docstring de clase actualizados.

### Documentación (drift)

16. `README.md` — contrato de login `{"password": "..."}`, "contraseña del panel" en lugar de "clave", eliminado "Cuando `SECURITY_MODE=protected`", tabla de `/api/auth/status` con `security_enabled`, y aclarado que `ADMIN_API_KEY` queda reservada para M2M/`X-API-Key`.
17. `docs/SECURITY.md` — filas/párrafos de `SECURITY_MODE` migrados al modelo `password_enabled` en SQLite / `security_manager.is_enabled()` (tabla de endpoints, exención loopback, §3 variables, dependencias, ejemplo `.env`, checklist §7, §8 primera instalación, §9 runtime).
18. `docs/ARCHITECTURE.md` — tabla `/api/auth/status` → `security_enabled`; contrato de login; clasificación AUTH/PROTECTED; §5.3 handshake; §7 flujo de autenticación (texto y diagrama ASCII).
19. `docs/CONTEXT.md` — nota de Fase 7a sin `SECURITY_MODE` (el estado real se persiste en SQLite).
20. `docs/deploy/runbook.md` — registro de ejecución, tabla "Modelo de seguridad", instrucción de producción y valores `.env` migrados al modelo de contraseña del panel (activación desde la UI).
21. `docs/deploy/INICIO.md` — fila del workstream B, P0-2 y detalle H1 sin `SECURITY_MODE`.

### Nuevo

22. `docs/deploy/handoffs/FASE8_F4_DRIFT.md` — este documento.

## Resultado de verificación

- **pytest**: `python -m pytest backend/tests display/tests -q`
  → `393 passed, 9 skipped` (5 warnings preexistentes de corutina no esperada en
  `restore_from_db`, no relacionados con este cambio).
- **ruff**: `python -m ruff check backend display scripts --config backend/pyproject.toml`
  → `All checks passed!`
- **mypy**: `python -m mypy app --config-file pyproject.toml` (desde `backend/`)
  → `Success: no issues found in 31 source files`
- **vitest**: `npm run test` (desde `frontend/`) → `27 passed (3 files)`.
- **build**: `npm run build` (desde `frontend/`) → verde (`tsc -b && vite build`,
  `✓ 103 modules transformed`, sin errores).

## Grep final

`SECURITY_MODE`/`security_mode` ya **no** aparece en `backend/`, `frontend/src`,
`.env.example` ni `frontend/.env.example`.

Las únicas menciones restantes son permitidas:

- `docs/deploy/handoffs/FASE1_*` … `FASE7_*` y `FASE8_*` — registros históricos y
  handoffs nuevos (no se reescriben por indicación del objetivo).
- `docs/archive/**` — registros históricos (no se tocan).
- Fuera de alcance de esta fase (no se editan): `docs/audits/auditoria-externa-2026-08-21.md`,
  `docs/PREMISAS_ESENCIALES.md`, `docs/PLAN_CIERRE_V1.md`,
  `docs/deploy/ESTADO_DESPLEGUE.md`.

## Decisiones

- Renombrado `security_mode` → `security_enabled` (booleano) en `GET /api/auth/status`
  porque el campo ya no tiene dos "modos" con semántica propia: ahora es un flag
  binario derivado de `security_manager.is_enabled()`. Se propaga al frontend para
  mantener el contrato verificable (TypeScript estricto).
- Los fixtures `protected_mode` de los tests siguen activando la protección con
  `security_manager.set_enabled(True)` (patrón ya existente) y conservan el
  `monkeypatch` de `admin_api_key`; solo se retira el monkeypatch de `security_mode`.
- `test_login_works_without_admin_key` ahora también activa la protección
  (`set_enabled(True)`) para mantener la intención del test: el login funciona
  aunque `ADMIN_API_KEY` esté vacía (usa la contraseña del panel, no la key M2M).
- No se tocaron `backend/app/services/state_manager.py`, `main.py`, `display/`, ni la
  ortografía "contrasena"→"contraseña" (otra fase). El único cambio en
  `persistence.py` es el docstring indicado.

## TEXTO DE PASO

```
Fase 4 del refactor 0.4.0 completada (eliminación de SECURITY_MODE + corrección del
contrato de login). Rama main, commit base 901d21b, versión 0.3.4 -> objetivo 0.4.0.
Sin commit.

Hecho en esta fase:
- Eliminado el campo security_mode de backend/app/config.py (docstring, campo y rama
  de model_post_init). .env.example sin SECURITY_MODE.
- backend/app/api/deps.py, network.py, auth.py, services/security_manager.py y
  services/persistence.py: docstrings/comentarios migrados al mecanismo real
  (security_manager.is_enabled(), password_enabled persistido en SQLite).
- GET /api/auth/status: campo security_mode -> security_enabled (booleano).
- Frontend: AuthStatus.security_enabled (boolean) en useApi.ts; signal securityEnabled
  en App.tsx; comentarios de useWebSocket.ts y frontend/.env.example actualizados.
- Tests: test_security.py, test_auth.py, test_hmi.py y test_ws_endpoint.py sin
  monkeypatch de security_mode (usan security_manager.set_enabled(True)); aserciones
  security_enabled is True/False.
- Docs: README.md, docs/SECURITY.md, docs/ARCHITECTURE.md, docs/CONTEXT.md,
  docs/deploy/runbook.md y docs/deploy/INICIO.md migrados al nuevo modelo
  "Panel security: disabled/enabled, persistente en SQLite"; contrato de login
  {"password"} y "contraseña del panel".

Verificación:
- pytest backend/tests display/tests: 393 passed, 9 skipped.
- ruff: All checks passed.
- mypy (desde backend/): Success, 31 source files.
- vitest: 27 passed (3 files). npm run build: verde.

Grep final: sin SECURITY_MODE/security_mode en backend/, frontend/src, .env.example ni
frontend/.env.example. Quedan solo en docs/archive/**, handoffs FASE1_*...FASE7_* y
FASE8_* (permitidos) y en docs fuera de alcance (auditoria-externa, PREMISAS_ESENCIALES,
PLAN_CIERRE_V1, ESTADO_DESPLEGUE).

Continuar con la siguiente fase del refactor a 0.4.0.
```
