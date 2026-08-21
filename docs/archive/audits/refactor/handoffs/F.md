# Handoff F — Docs/consistencia (SECURITY.md, README, .env.example, versiones)

## Resultado
Completado (5/5 tareas). Sin saturación.

1. **`docs/SECURITY.md`** (nuevo): modelo de amenazas y política de seguridad
   explícita — clasificación de endpoints (PUBLIC / LOCAL / PROTECTED / ADMIN),
   `SECURITY_MODE=local|protected` + `ADMIN_API_KEY`, advertencia de RCE en
   `POST /admin/ssh/execute`, regla sudoers mínima (`pi → /usr/bin/nmcli`) y
   safe-state (arranque / fallo / apagado limpio).
2. **`README.md`**: conteo de tests unificado a **278 tests (4 skipped)** con fecha
   de verificación (2026-08-20). Eliminadas las cifras inconsistentes (~180, ~222,
   ~277 y la tabla "Cobertura por área" cuyo Total=277 quedaba stale). Añadida la
   sección "Configuración de desarrollo" documentando `VITE_API_URL` (default
   `http://localhost:8000`). Verificado que NO queda referencia errónea a
   "LED en GPIO17" (las menciones actuales a GPIO 17 son correctas: es el IRQ del
   touch, "NO conectar un LED aquí").
3. **`frontend/.env.example`** (nuevo): `VITE_API_URL=http://localhost:8000` con
   comentario explicativo (solo afecta al proxy de `vite dev`; en producción el
   frontend se sirve desde el backend, mismo origen).
4. **Versiones alineadas a `0.3.0`** (sin subir versión): `VERSION`, `main.py`
   (`version=` y JSON del root) y `frontend/package.json` ya estaban en `0.3.0`.
   Único drift corregido: banner de `display/app.py` `v0.1` → `v0.3.0`.
5. Suite verde (ver §Verificación).

## Archivos modificados
- [nuevo] `docs/SECURITY.md` — modelo de amenazas + política de seguridad.
- [nuevo] `frontend/.env.example` — `VITE_API_URL` con comentario.
- [nuevo] `docs/audits/refactor/handoffs/F.md` — este handoff.
- [editado] `README.md` — conteo de tests unificado + sección VITE_API_URL.
- [editado] `display/app.py` — solo la cadena de versión del banner `v0.1` → `v0.3.0`.

No tocados: `package-lock.json` (no imprescindible), `backend/app/*`, resto de
`display/*`, y el feedback del botón / wiring de pantalla de `display/app.py`.

## Verificación ejecutada
- `python -m pytest display/tests/ -q` → **58 passed, 2 skipped** (0 fallos).
- `python -m pytest backend/tests/ display/tests/ -q` → **278 passed, 4 skipped**
  (1 warning preexistente en `test_restore_from_db_sets_led_and_button`).
- `cd frontend && npm run build` → **verde** (`tsc -b` + `vite build`, 99 módulos).
- `ReadLints` implícito: los cambios son solo texto/markdown/cadenas; sin impacto de tipos.

## Decisiones tomadas
1. **Conteo único = 278 tests (4 skipped)**, con fecha 2026-08-20. Es la cifra de
   `pytest backend/tests/ display/tests/`. Se eliminó la tabla "Cobertura por área"
   porque su Total (277) ya no era fiel y no se podía re-derivar con precisión sin
   reintroducir una segunda cifra.
2. **`display/app.py`**: solo se alineó el banner `v0.1` → `v0.3.0`. Se dejaron
   intactos `version="v1.2"` (etiqueta del `HeaderWidget`) y `"version": "1.0"`
   (protocolo del subscribe WS): son versiones de UI/protocolo, no la versión del
   paquete `0.3.0`. Cambiarlos habría tocado el wiring de pantalla / protocolo.
3. **`VITE_API_URL` solo afecta al proxy de desarrollo** (`vite.config.ts`); el
   frontend usa rutas relativas (`/api`, `ws://<host>/ws`) y en producción se sirve
   desde el backend (mismo origen). Documentado así para no inducir a error.
4. **Safe-state documentado sin inventar**: LED actualmente virtual (`pin: null`);
   arranque = `restore_from_db()`; fallo = sin reset (conserva último estado);
   apagado = `flush_pending_tasks()` + `close_persistence()` + `gpio_service.cleanup()`.
5. **No se tocó `package-lock.json`** (la versión raíz ya fue alineada por D).

## Riesgos / pendientes
- `SECURITY_MODE=protected` no cubre `/admin/*`: `ssh.py`/`deploy.py` mantienen su
  propio `_verify_api_key` y exigen `X-API-Key` siempre (independiente de
  `SECURITY_MODE`). Documentado en `SECURITY.md` §2/§3 y ya registrado como
  pendiente cross-workstream en `ESTADO.md` (consolidar en `require_admin_api_key`).
- El badge de Shields usa el texto `278 tests (4 skipped)` sin URL-encoding de los
  paréntesis; es funcional en navegadores modernos, pero si se quiere estricto usar
  `%28`/`%29`.
- La cifra "278 (4 skipped)" es la de pytest (backend+display). Vitest (16/16) y
  `npm run build` son verificaciones separadas del frontend, no sumadas a esa cifra.

## Texto de paso al siguiente agente
Workstream F completo y en verde. No queda trabajo pendiente dentro del alcance.

Para el orquestador / siguientes agentes:
- No revertir la unificación del conteo de tests a la única cifra `278 (4 skipped)`
  ni re-añadir la tabla "Cobertura por área" (stale).
- No "corregir" `version="v1.2"` del header ni `"version": "1.0"` del WS: no son la
  versión del paquete.
- Si se consolida `_verify_api_key` de `ssh.py`/`deploy.py` en `require_admin_api_key`,
  actualizar `docs/SECURITY.md` §2/§3 en consecuencia.
