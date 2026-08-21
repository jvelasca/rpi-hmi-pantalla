# FASE 1 — Handoff de entrada: Auth por session-cookie (P0)

> Handoff de entrada para el subagente que ejecuta la Fase 1 del
> `docs/PLAN_CIERRE_V1.md`. Lee `docs/PREMISAS_ESENCIALES.md` antes de empezar.
>
> Fecha: 2026-08-20 · HEAD: `881ec1a` · Versión: 0.3.1

## 1. Contexto verificado (no inventes nada fuera de esto)

- Proyecto: **RPi HMI** — backend FastAPI (`backend/`) + display Pygame (`display/`) +
  frontend SolidJS (`frontend/`). LAN de confianza, V1 **no en producción**.
- Working dir: `e:\SINCRONIZADO\Informatica\Proyectos VisualStudio\Python\Rapsberry\Rpi_Pantalla_V1`
- Entorno: Python 3.13.7, pytest 8.4.2; node 22.14, npm 10.9.
- **Baseline verde:** `pytest backend/tests/ display/tests/` = **332 passed / 9 skipped**;
  `npm test` (frontend) = **26 passed**.
- Versión única en `VERSION` → `backend/app/_version.py` (fallback `0.3.1`).

## 2. Problema a corregir (P0)

`VITE_API_KEY` se inyecta en el bundle del navegador:

- `frontend/src/hooks/useWebSocket.ts:29` → `const API_KEY = import.meta.env.VITE_API_KEY`
- `frontend/src/hooks/useApi.ts:22` → `const API_KEY = import.meta.env.VITE_API_KEY`

Vite lo sustituye literalmente en `frontend/dist/assets/index-*.js`, servido por
FastAPI en `/`. Cualquier host de la LAN que cargue el panel lee la clave, anulando
la protección `X-API-Key` en `SECURITY_MODE=protected`.

## 3. Solución aprobada (Opción A) — session-cookie HttpOnly

El navegador deja de llevar la API key. En su lugar:

1. Login explícito: `POST /api/auth/login` recibe la `ADMIN_API_KEY` (body JSON),
   la valida con `secrets.compare_digest` y emite una **cookie de sesión HttpOnly**.
2. `POST /api/auth/logout` invalida la sesión.
3. Las dependencias de auth (`require_admin_api_key` / WS) aceptan **X-API-Key**
   (scripts/M2M) **o** la cookie de sesión (navegador). Se mantiene la exención
   de loopback para el display local.
4. El frontend añade una pantalla mínima de login (sin guardar la key; la cookie es
   HttpOnly). En `SECURITY_MODE=local` el login no es obligatorio (no se exige auth).

## 4. Alcance de archivos

### Crear
- `backend/app/api/auth.py` — routers login/logout + gestión de sesión en memoria.
- `backend/tests/test_auth.py` — tests de login/logout/cookie/WS con cookie.

### Modificar
- `backend/app/api/deps.py` — validar cookie de sesión además de `X-API-Key`.
- `backend/app/api/ws.py` — aceptar cookie de sesión en el handshake (además de
  header/subprotocolo/`?token=`).
- `backend/app/api/__init__.py` — exportar `auth_router`.
- `backend/app/main.py` — registrar `auth_router` (siempre, sin feature-gate).
- `backend/app/config.py` — añadir setting de expiración de sesión si es necesario
  (p. ej. `SESSION_TTL_SECONDS`, default razonable) con docstring.
- `frontend/src/hooks/useApi.ts` y `frontend/src/hooks/useWebSocket.ts` — eliminar
  `VITE_API_KEY`; usar cookie (fetch y WS envían la cookie automáticamente).
- `frontend/src/` — añadir pantalla/estado de login mínima, coherente con el tema
  oscuro existente (`#141428`, Tailwind). Reutilizar `useApi`.
- `.env.example` (raíz) y `frontend/.env.example` — documentar el nuevo flujo,
  quitar `VITE_API_KEY`.
- `docs/SECURITY.md` — documentar el nuevo modelo de auth (cookie navegador /
  X-API-Key M2M).

### NO tocar (fuera de alcance)
- `backend/config/devices.yaml`, GPIO, `display/`, `persistence.py`, `systemd/*`,
  versionado (`0.3.2` se hace en Fase 5), limpieza de `legacy/` (Fase 3).

## 5. Restricciones de implementación

- **Sesión en memoria** (dict con token → expiración) + token **firmado con HMAC**
  (no hace falta dependencia nueva: usar `hmac` + `secrets` stdlib; si `itsdangerous`
  ya está en requirements, úsalo). Clave de firma derivada de `ADMIN_API_KEY` +
  un secreto aleatorio por arranque. Cookie con `HttpOnly` y `SameSite=Strict`;
  `Secure` solo si hay TLS (documentar la limitación LAN).
- Mantener el modelo de seguridad existente: `SECURITY_MODE=local` no exige auth;
  loopback exento en `protected`. La cookie solo se exige a clientes no-loopback en
  `protected`, igual que `X-API-Key`.
- El WS ya recibe `websocket.headers` (Mapping); la cookie llega en el header
  `cookie`. Parsear manualmente (no añadir dependencias).
- Estilo: docstrings en español, `from __future__ import annotations`, módulo con
  docstring inicial. Sigue las convenciones de `deps.py`/`ws.py`/`hmi.py`.
- No romper los 332 tests existentes. No añadir comentarios triviales que narren el código.

## 6. Verificación obligatoria (antes de dar por terminado)

```bash
python -m pytest backend/tests/ -q --tb=short
ruff check backend/ --config backend/pyproject.toml
cd frontend && npm run build && npm test
```

Además, verificación manual opcional del flujo (con `SECURITY_MODE=protected`):
login → cookie → `POST /api/led/toggle` sin `X-API-Key` funciona; sin login → 401.

## 7. Definition of done

- [ ] Login/logout funcionan; cookie HttpOnly emitida y validada.
- [ ] REST mutador + WS aceptan cookie (navegador) o `X-API-Key` (M2M), loopback exento.
- [ ] `VITE_API_KEY` eliminado de `frontend/` y de los `.env.example`.
- [ ] Frontend muestra login cuando el backend responde 401 en `protected`.
- [ ] `test_auth.py` añadido y verde; suite completa (332 + nuevos) verde.
- [ ] `ruff` verde; `npm run build` y `npm test` verdes.
- [ ] `docs/SECURITY.md` y `.env.example` actualizados.

## 8. Entrega

Escribe `docs/deploy/handoffs/FASE1_AUTH_CIERRE.md` con el **documento de cierre**
siguiendo la plantilla de `docs/PREMISAS_ESENCIALES.md`, incluyendo el bloque
**TEXTO DE PASO** para la Fase 2 (sincronizar documentación).
