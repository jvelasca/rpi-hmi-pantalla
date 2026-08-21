# Auditoría externa — Veredicto y plan de corrección (2026-08-21)

> Registro del veredicto de la auditoría externa recibido el 2026-08-21, junto
> con las observaciones adicionales del usuario. Es la fuente de verdad del
> alcance del refactor objetivo **0.4.0**.
>
> Auditoría sobre `main` en **0.3.3** (commit `17a2967`). El árbol de trabajo
> local está en **0.3.4** sin commitear (ver `docs/audits/baseline-2026-08-21.md`).

## Veredicto

**9,1/10** — muy cerca de cerrar, pero no al 100 %. Se confirma un problema de
seguridad real que debe corregirse antes de declarar la app cerrada, más una
inconsistencia documental y mejoras menores.

## 🔴 1. Seguridad fail-open si SQLite no está disponible (P1 — crítico)

En `backend/app/main.py` el arranque de SQLite está envuelto en
`try/except Exception` que solo registra un `warning` y **continúa**. Combinado
con el estado inicial de `SecurityManager` (`_enabled=False`), un sistema que
tenía la seguridad activada arranca **desprotegido** si SQLite falla
(corrupto / no montado / permisos).

Corrección decidida: SQLite es un componente esencial → si falla, el backend
**no entra en READY** y `systemd` reinicia; además `SecurityManager` debe
distinguir primer arranque (disabled) de sistema existente ilegible
(fail-closed).

## 🟠 2. README desactualizado respecto al contrato de login (P1)

El README documenta `POST /api/auth/login` con `{"api_key": "..."}` y habla de
"clave", pero el backend exige `{"password": "..."}` (`LoginRequest.password`) y
el frontend envía `password`. Terminología: usar "contraseña del panel" y
reservar "API key" para `ADMIN_API_KEY` / `X-API-Key` / M2M.

## 🟠 3. `SECURITY_MODE` con significado distinto al documentado (P1)

`config.py` aún define `SECURITY_MODE=local|protected`, pero el estado real de
protección es `security_manager.is_enabled()` (persistido en SQLite). `deps.py`,
`network.py` y el README siguen documentando `SECURITY_MODE` como si gobernara
la protección. Decisión: **eliminar `SECURITY_MODE`** y documentar
"Panel security: disabled/enabled, persistente en SQLite".

## 🟢 Confirmado correcto (no requiere cambios)

- `1234` no puede activar protección (`409` + cambio obligatorio). ✅
- Cambio de contraseña revoca sesiones (`session_manager.clear()`). ✅
- PBKDF2-HMAC-SHA256 (120k iter, salt 16B, `compare_digest`). ✅
- Rate-limit login (5 intentos / 300 s / por IP, solo fallos). ✅
- Cookie HttpOnly, SameSite=Strict, Path=/, Max-Age=TTL, Secure si HTTPS. ✅
- `?token=` eliminado del WebSocket. ✅
- Frontend usa `credentials: "include"`. ✅
- `VITE_API_KEY` inexistente. ✅
- REST HMI protegido (`require_admin_api_key`). ✅
- `/admin/*` aislado (`require_admin_api_key_always`). ✅
- WebSocket handshake sólido (loopback/cookie/X-API-Key/subprotocolo; 4401). ✅
- Sequence tracking / resync correcto. ✅
- `WebSocketHub` con cola acotada (`BROADCAST_QUEUE_MAXSIZE=100`, drop-oldest). ✅
- REST display protegido. ✅
- Frontend limpio (App/useApi/useWebSocket/useConnectionMonitor/sequenceTracker). ✅
- CI bien diseñado. ✅
- Versionado 0.3.3 coherente. ✅
- Arquitectura física (GPIO20/21, GPIO17=TP_IRQ). ✅
- Persistencia y arranque coherentes (salvo el fail-open señalado). ✅

## Conclusión y siguiente paso

Corregir fail-open + limpiar drift `SECURITY_MODE`/README y **no refactorizar
más**. La siguiente auditoría debe ser **exclusivamente HIL** sobre la Pi real
(apagado brusco, reboot, SQLite corrupta/inaccesible, arranque systemd, watchdog,
touch, DRM, pérdida de red, cambio de IP, login/logout y recuperación).

## Observaciones adicionales del usuario (incluidas en el alcance)

1. **Dos LEDs**: el botón On/Off actúa sobre su LED (GPIO 20) y se indica en
   pantalla/webserver; el pulsador actúa **solo** sobre su LED (GPIO 21). Hoy
   `press_button()` apaga también el del On/Off (bug en `state_manager.py`).
2. El On/Off debería ser **tipo interruptor** (no botón "apagar").
3. "contraseña" se escribe con **Ñ** (no "contrasena").
