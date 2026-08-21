# FASE 7 CIERRE — Seguridad (7a) + GPIO (7b) + Display (7c)

Versión final: **0.3.4**. Esta fase atiende la auditoría externa y la petición
del usuario sobre la Fase 6.

## Qué se hizo

### 7a — Seguridad (backend + web)

- **Contraseña OFF por defecto.** `SecurityManager` arranca con `_enabled=False`
  (ya no depende de `settings.security_mode`). La migración 003 siembra
  `password_enabled=0`; la nueva **migración 004** (`UPDATE security_settings SET
  password_enabled = 0`) resetea instalaciones previas. Resultado: la web **no**
  pide contraseña al cargar.
- **Forzar cambio de `1234` antes de activar** (P1). `POST /api/auth/security`
  devuelve `409` si `enabled=true` y la contraseña sigue siendo la de fábrica.
  Mínimo de contraseña subido de 4 → **8 caracteres** (`POST /api/auth/password`).
- **WS sin `?token=`** (P2). `_extract_api_key_candidates` ya no lee el query
  string. Fuentes válidas: header `X-API-Key`, `Sec-WebSocket-Protocol`, cookie.
- **`credentials: "include"`** en `fetch()` (P2).

### 7b — GPIO (hardware)

- `devices.yaml`: `led1` → **GPIO 20** (LED botón On/Off, deja de ser virtual);
  nuevo `led_button` → **GPIO 21** (`role: button_led`, LED del pulsador).
- `StateManager`: nuevo `set_updater_button`; `press_button`/`release_button`
  invocan el callback con el booleano de pulsación.
- `main.py` (lifespan): detecta ambos pines por `kwargs.role`, hace
  `setup_output` de ambos y registra `set_updater` (LED) y `set_updater_button`.

### 7c — Display físico (Pygame)

- Nueva vista `"security"` y clase `SecuritySettingsView` con teclado numérico
  en pantalla (0-9 + BORRAR + LIMPIAR), campos actual/nueva/confirmar, y botones
  ACTIVAR/DESACTIVAR + CAMBIAR.
- El overlay de CONFIGURACION pasa de 5 a **6** opciones (añade "Contraseña").
- Validación en cliente: bloqueo de activación con `is_default` ("Debes cambiar
  la contraseña de fábrica (1234) antes de activar"), mínimo 8 y coincidencia
  nueva/confirmar. El backend refuerza con 409/422.
- **Limitación:** el teclado del display es numérico; para contraseñas
  alfanuméricas usar la web.

## Contrato de API (para clientes)

- `GET /api/auth/security` → `{enabled: bool, is_default: bool}` (arranca en
  `enabled: false`).
- `POST /api/auth/security` → `{enabled, current?}`. `401` sin autorización,
  `409` al activar con `1234`, `200` con `{enabled, is_default}`.
- `POST /api/auth/password` → `{current, new}` con `new` mínimo 8 (si no, `422`).
- `WS /ws`: `?token=` eliminado; fuentes válidas `X-API-Key`, cookie,
  `Sec-WebSocket-Protocol`. Fallo → close code `4401`.

## Verificación

- Backend: `pytest` 312 passed / 7 skipped.
- Display: `pytest` 79 passed / 2 skipped.
- Frontend: `vitest` 27 passed + `npm run build` OK.
- Ruff: limpio.

## Pendiente del orquestador

- Deploy físico a la Pi (copiar backend + frontend/dist + display + devices.yaml,
  reiniciar `rpi-hmi-backend` y `rpi-hmi-display`).
- Verificar en vivo: `GET /api/auth/security` → `enabled:false`;
  activar con `1234` → 409; cambiar a personalizada y activar → ok.
- Bump a `0.3.4` (ya aplicado) + commit/push.
