# FASE 7a/7b — Cierre de seguridad + habilitación GPIO20/21

Estado de partida: versión `0.3.3`. Tras la Fase 6 (gestión de contraseña del
panel) una auditoría externa y el usuario piden:

1. **Contraseña OFF por defecto** (hoy arranca "protegida" si
   `SECURITY_MODE=protected`, y la Pi lo tiene así → la web pide login al cargar).
2. **Forzar cambio de `1234` antes de activar** (P1) + mínimo **8 caracteres**.
3. **Eliminar `?token=`** del WebSocket (P2).
4. **`credentials: "include"`** en `fetch()` (P2).
5. **GPIO20 = LED del botón On/Off** y **GPIO21 = LED del pulsador**.

Este documento es la entrada para el subagente que implementa 7a (seguridad +
web) y 7b (GPIO). No incluye el menú de contraseña en el display Pygame
(eso es la Fase 7c, otro subagente).

---

## Objetivo

- La web NO debe pedir contraseña al cargar (estado de fábrica = abierta).
- El usuario puede activar la protección desde Configuración, pero **si la
  contraseña sigue siendo `1234`, no se permite activar**: debe poner una
  contraseña personalizada (mín. 8 caracteres) primero.
- El WebSocket deja de aceptar credencial por query string.
- `fetch()` envía cookies de forma explícita.
- El LED principal pasa de "virtual" a GPIO20; se añade un LED de pulsador en
  GPIO21.

## Cambios backend

### 1. `backend/app/services/security_manager.py`

- `__init__`: `self._enabled: bool = False` (quitar `settings.security_mode == "protected"`).
- `reset()`: `self._enabled = False` (quitar `settings.security_mode == "protected"`).
- Si el import `from backend.app.config import settings` queda sin uso, eliminarlo.
- Actualizar docstrings (módulo, clase, `reset`) para reflejar que el estado
  por defecto es **desactivado** y que `SECURITY_MODE` ya no lo gobierna.

### 2. `backend/app/services/persistence.py`

- `_migration_003`: cambiar `enabled = 1 if settings.security_mode == "protected" else 0`
  por `enabled = 0`. Eliminar el import `from backend.app.config import settings`
  (quedará sin uso; conservar el import de `password_hash`). Actualizar docstring.
- Añadir migración **004** y registrarla en `_MIGRATIONS`:
  - tupla `(4, "reset_password_enabled", "_migration_004")`.
  - `_migration_004`: `await self._conn.execute("UPDATE security_settings SET password_enabled = 0")`
    con docstring explicando que resetea instalaciones previas al nuevo
    comportamiento "off por defecto".

### 3. `backend/app/models/security.py`

- `ChangePasswordRequest.new`: `min_length=4` → `min_length=8`. Actualizar
  descripción del Field y el docstring de la clase.

### 4. `backend/app/api/auth.py`

- En `set_security` (`POST /api/auth/security`), justo después de la
  autorización y antes de `await security_manager.set_enabled(...)`, añadir:

```python
if body.enabled and security_manager.is_default_password():
    return JSONResponse(
        status_code=409,
        content={"detail": "Debes cambiar la contraseña de fábrica (1234) antes de activar la protección."},
    )
```

- Actualizar el docstring de `set_security` para documentar el 409.
- (No tocar `login`, `logout`, `status`, `change_password` salvo el docstring
  de `change_password` si menciona "mínimo 4": ahora es 8.)

### 5. `backend/app/api/ws.py`

- En `_extract_api_key_candidates`, **eliminar** el bloque de query param:

```python
query = websocket.scope.get("query_string", b"")
parsed = urllib.parse.parse_qs(query.decode("utf-8"))
candidates.extend(parsed.get("token", []))
```

- Eliminar `import urllib.parse` (quedará sin uso).
- Actualizar docstrings (módulo, `_extract_api_key_candidates`,
  `websocket_endpoint`) para reflejar que las fuentes de autenticación son
  `X-API-Key`, `Sec-WebSocket-Protocol` y cookie de sesión (ya NO `?token=`).

## Cambios frontend web

### 6. `frontend/src/hooks/useApi.ts`

- Añadir `credentials: "include"` a las opciones de `fetch` en `get` y en
  `postJson`.

### 7. `frontend/src/components/SecuritySettings.tsx`

- En `changePassword`: validación `newPwd().length < 4` → `< 8`, mensaje
  "al menos 8 caracteres".
- Placeholder "Minimo 4 caracteres" → "Minimo 8 caracteres".
- En `toggleSecurity`, al **activar** (`target === true`) y
  `status()?.is_default` es true: NO llamar a la API; mostrar error
  "Debes cambiar la contraseña de fábrica (1234) antes de activar la protección."
  (el backend además responde 409 como defensa en profundidad).
- Ajustar cualquier texto/label coherente con el mínimo de 8.

## Cambios GPIO (7b)

### 8. `backend/config/devices.yaml`

- Sustituir el comentario de cabecera sobre "LEDs virtuales" por uno que
  documente los dos LEDs físicos.
- `led1`: `pin: {bcm: 20, name: "LED_BOTON_ONOFF"}`, conservar
  `kwargs: {role: led}` (quitar `virtual: true`).
- Añadir un segundo dispositivo:

```yaml
  - id: led_button
    type: digital_output
    name: "LED PULSADOR"
    pin:
      bcm: 21
      name: "LED_PULSADOR"
    kwargs:
      role: button_led
```

### 9. `backend/app/services/state_manager.py`

- Añadir `self._updater_button_callback: Any | None = None` en `__init__`
  (junto a `_updater_callback`).
- Añadir método `set_updater_button(self, callback: Any) -> None` con docstring
  (callback con firma `callback(device: str, pressed: bool)`).
- En `press_button()`, después de construir `new_state` (pressed=True) y antes
  del broadcast, invocar el callback del botón con `("button", True)` (envuelto
  en try/except como el callback de LED).
- En `release_button()`, tras construir `new_state` (pressed=False), invocar
  `("button", False)`.

### 10. `backend/app/main.py` (lifespan, bloque GPIO)

Sustituir el bucle actual de detección de un único `led_pin` por la detección
de DOS pines según `kwargs.role`:

```python
led_pin = 0
button_led_pin = 0
for dev in devices.values():
    if dev.type == DeviceType.DIGITAL_OUTPUT and dev.pin:
        role = dev.kwargs.get("role")
        if role == "led":
            led_pin = dev.pin.bcm
        elif role == "button_led":
            button_led_pin = dev.pin.bcm

if led_pin > 0:
    gpio_service.setup_output(led_pin)
    logger.info("GPIO %d configurado como salida (LED)", led_pin)
if button_led_pin > 0:
    gpio_service.setup_output(button_led_pin)
    logger.info("GPIO %d configurado como salida (LED pulsador)", button_led_pin)
```

Conservar el callback `_update_led` existente y añadir:

```python
def _update_button(device: str, pressed: object) -> None:
    if button_led_pin > 0:
        gpio_service.set_state(button_led_pin, bool(pressed))

state_manager.set_updater(_update_led)
state_manager.set_updater_button(_update_button)
```

- Mantener el `else` de aviso "LED virtual" solo si `led_pin == 0`.

## Tests

- `backend/tests/test_migrations.py`: versión de esquema esperada 3 → 4.
- `backend/tests/test_security.py`: añadir tests para
  - estado por defecto desactivado (`security_manager.is_enabled()` es False tras `reset`),
  - `POST /api/auth/security` con `enabled=true` y contraseña por defecto → 409,
  - `POST /api/auth/password` con `new` de menos de 8 → 422.
- `backend/tests/test_ws_endpoint.py`: añadir/quitar test para asegurar que
  `?token=` ya no autentica (una conexión con `?token=<admin_api_key>` desde
  un host no-loopback debe rechazarse con 4401).
- `backend/tests/test_state_manager.py` / `test_hmi.py`: revisar y actualizar
  cualquier assert sobre `gpio_pin == 0` (ahora `_load_led_pin()` devuelve 20).
- Añadir test de `set_updater_button` (callback invocado en press/release con
  el booleano correcto) y de carga de `led_button` (pin 21) desde devices.yaml.
- `frontend/src/tests/components.test.tsx`: revisar/ajustar tests de
  `SecuritySettings` si validan el mínimo de 4 → 8.

## Verificación (ejecutar y dejar en verde)

- Backend: `cd backend && python -m pytest -q`
- Frontend: `cd frontend && npm run build` y `npm test` (vitest)
- Ruff (si está configurado en el repo): respetar estilo existente.

## Documentación

- Actualizar `docs/SECURITY.md` y `docs/ARCHITECTURE.md` en lo que toque a:
  - contraseña OFF por defecto,
  - mínimo 8 caracteres y flujo de activación forzada,
  - WS sin `?token=`,
  - GPIO20/21 en devices.yaml.

## NOTAS

- No modificar `VERSION` ni hacer bump de versión (lo hace el agente orquestador
  al final de la Fase 7).
- No tocar `display/` (eso es Fase 7c).
- Mantener docstrings en español y estilo coherente con el resto del código.
