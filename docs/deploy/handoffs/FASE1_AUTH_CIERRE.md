# FASE 1 — Auth por session-cookie HttpOnly (P0) — CIERRE

- Rama/base: `main` @ `881ec1a` (sin commitear; cambios en working tree)
- Versión: 0.3.1
- Resumen: Se elimina la exposición de `ADMIN_API_KEY` en el bundle del navegador
  (antiguo `VITE_API_KEY`) sustituyéndola por login explícito con **cookie de
  sesión HttpOnly** (Opción A). REST mutador y WebSocket aceptan ahora `X-API-Key`
  (scripts/M2M) **o** cookie de sesión (navegador); loopback sigue exento.

## Cambios

### Creados
- `backend/app/api/auth.py` — routers `POST /api/auth/login`, `POST /api/auth/logout`
  y `GET /api/auth/status` + `SessionManager` en memoria (dict `token→expiración`).
  Token firmado HMAC-SHA256 (stdlib `hmac`+`secrets`) con clave derivada de
  `ADMIN_API_KEY` + secreto aleatorio por arranque. Cookie `HttpOnly; SameSite=Strict`;
  `Secure` solo si HTTPS. Incluye helpers de parseo de cookie para REST y WS.
- `backend/tests/test_auth.py` — 14 tests: login (clave correcta/incorrecta/vacía),
  atributos de cookie, logout revoca, auth/status, mutador REST con cookie/X-API-Key,
  cookie alterada, loopback exento, WS con cookie/X-API-Key y WS rechazado sin auth.
- `frontend/src/components/LoginScreen.tsx` — pantalla de login mínima (tema oscuro
  `#141428`/`#0f0f23`), envía la clave a `/api/auth/login` sin guardarla en JS.

### Modificados
- `backend/app/api/deps.py` — `require_admin_api_key` y `require_admin_api_key_always`
  aceptan cookie de sesión además de `X-API-Key`; `require_admin_api_key_always`
  ahora recibe `request` (inyectado por `Depends`). Añadido `_has_valid_session`.
- `backend/app/api/ws.py` — el handshake valida la cookie de sesión (parseo manual
  del header `Cookie`) además de header/subprotocolo/`?token=`.
- `backend/app/api/__init__.py` — exporta `auth_router`.
- `backend/app/main.py` — registra `auth_router` siempre (sin feature-gate).
- `backend/app/config.py` — nuevo setting `SESSION_TTL_SECONDS` (default `28800`,
  ge=60) con docstring; descripción de `security_mode` actualizada.
- `backend/tests/test_config.py` — test existente de `require_admin_api_key_always`
  adaptado a la nueva firma (pasa `request` simulado); imports reordenados.
- `frontend/src/hooks/useApi.ts` — eliminado `VITE_API_KEY`/`authHeaders()`; añadidos
  `getAuthStatus`, `login`, `logout` y señal `unauthorized` (se activa ante 401).
- `frontend/src/hooks/useWebSocket.ts` — eliminado `VITE_API_KEY`; subprotocolo fijo
  `["rpi-hmi"]` (la cookie viaja sola en el handshake); añadido método `reconnect()`.
- `frontend/src/App.tsx` — estado de auth (`securityMode`/`authenticated`), carga
  `/api/auth/status` al montar, muestra `LoginScreen` en `protected` sin sesión,
  reconecta WS tras login y maneja logout.
- `frontend/src/components/Header.tsx` — botón "Salir" (logout) cuando hay sesión.
- `.env.example` — documenta flujo login/cookie y añade `SESSION_TTL_SECONDS`.
- `frontend/.env.example` — elimina `VITE_API_KEY`; documenta el nuevo flujo.
- `docs/SECURITY.md` — nuevo modelo de auth (cookie navegador / X-API-Key M2M),
  endpoints AUTH, sección "Modelo de sesión" y variables `SESSION_TTL_SECONDS`.

## Verificación

- `pytest backend/tests/ display/tests/ -q --tb=short` → **346 passed / 9 skipped**
  (baseline 332 + 14 nuevos de `test_auth.py`).
- `pytest backend/tests/ -q --tb=short` → **282 passed / 7 skipped**.
- `ruff check backend/ --config backend/pyproject.toml` → **verde** (All checks passed).
- `npm run build` (frontend) → **verde** (102 módulos, `tsc -b` + vite sin errores).
- `npm test` (vitest) → **26 passed** (3 ficheros).

## Decisiones

- **Sesión en memoria + HMAC stdlib**: no se añade `itsdangerous` (no está en
  `requirements.txt`). El token `sid.hmac` (base64url) se firma con una clave
  derivada de `ADMIN_API_KEY` + secreto por arranque; reiniciar el proceso o rotar
  la clave invalida todas las sesiones.
- **`require_admin_api_key_always` ahora recibe `request`**: necesario para aceptar
  cookie en `/admin/*`; los endpoints lo usan vía `Depends()`, así que FastAPI
  inyecta `request` automáticamente. Se adaptó el único test directo.
- **`GET /api/auth/status` público** (sin secretos): permite al frontend saber si
  está en `protected` y si hay sesión, evitando mostrar login innecesariamente en
  `local`. No revela la clave.
- **`SameSite=Strict` + `HttpOnly`; `Secure` solo con HTTPS**: limitación LAN
  documentada (sin TLS la cookie viaja en claro); no exponer el puerto 8000 a Internet.
- **Login con clave vacía devuelve 401** (no 422): se retira `min_length=1` del
  modelo para que el flujo de auth responda uniformemente con 401 a claves inválidas.

## Pendientes / fuera de alcance

- **Versionado** (`0.3.2`), **limpieza de `legacy/`** y **sincronización de
  `docs/ARCHITECTURE.md`/`README.md`**: Fases 2/3/5 (no tocadas).
- **Rate-limiting del login** (anti brute-force): queda para la Fase 4.
- `docs/CONTEXT.md` ya estaba modificado antes de esta fase (baseline del
  orquestador); no se ha tocado aquí.
- No se han tocado `backend/config/devices.yaml`, GPIO, `display/`, `persistence.py`,
  `config/systemd/*`.
- El frontend compilado (`frontend/dist/`) se regeneró con `npm run build` pero no
  se commitea (ignorado).

## TEXTO DE PASO (pegar en el siguiente chat)

"Proyecto en `881ec1a` (working tree, sin commit). Fase 1 completada: auth por
session-cookie HttpOnly (Opción A). Se creó `backend/app/api/auth.py`
(login/logout/status + SessionManager HMAC en memoria), `backend/tests/test_auth.py`
(14 tests) y `frontend/src/components/LoginScreen.tsx`; se modificaron `deps.py`,
`ws.py`, `__init__.py`, `main.py`, `config.py` (SESSION_TTL_SECONDS), `useApi.ts`,
`useWebSocket.ts`, `App.tsx`, `Header.tsx`, `.env.example`, `frontend/.env.example`
y `docs/SECURITY.md`. VITE_API_KEY eliminado del frontend. Verificación:
pytest backend+tests+display = 346 passed / 9 skipped (332 baseline + 14 nuevos);
ruff verde; npm build verde; vitest 26 passed. Pendientes: versionado 0.3.2 (Fase 5),
rate-limiting login (Fase 4), limpieza legacy/ (Fase 3). Siguiente fase: Fase 2 —
sincronizar documentación (reescribir docs/ARCHITECTURE.md con estructura/endpoints
reales y flujo de auth nuevo, actualizar README.md con conteos reales). Lee
docs/deploy/handoffs/FASE1_AUTH_CIERRE.md para el detalle."
