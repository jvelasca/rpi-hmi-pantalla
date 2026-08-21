# RPi HMI — Arquitectura del Sistema (v0.3.4)

> **Estado:** Implementado (V1, no en producción)  
> **Última actualización:** 2026-08-20  
> **Hardware:** Raspberry Pi Model B+ Rev 1.2 (BCM2835 ARMv6, 512MB RAM)  
> **Display:** 3.5" ILI9486 480x320 SPI + XPT2046 Touch

---

## 1. Visión general

Sistema HMI embebido autónomo para Raspberry Pi con doble interfaz de usuario:

| Interfaz | Tecnología | Propósito |
|---|---|---|
| **Display físico** (3.5" TFT) | Pygame + DRM/KMS | Panel de control táctil local |
| **Frontend web** | SolidJS + TypeScript | Control remoto desde navegador |

Ambos se comunican con un **único backend FastAPI** que abstrae el hardware (GPIO),
gestiona el estado del sistema, persiste en SQLite y expone REST + WebSocket.

```
+------------------ Raspberry Pi (autónoma) ----------------------+
|                                                                  |
|  +------------------------------------------------------------+ |
|  |           Backend FastAPI (Python 3.11 + tipado)           | |
|  |                                                            | |
|  |  * REST API  (/:8000/api/*, /admin/*)  Pydantic v2        | |
|  |  * WebSocket (/:8000/ws)             Estado en tiempo real | |
|  |  * Auth      (/:8000/api/auth/*)     Cookie de sesión      | |
|  |  * GPIO      (gpiozero)              Pin desde devices.yaml| |
|  |  * Persistencia SQLite               data/state.db         | |
|  |  * Frontend  (SolidJS compilado)     Servido desde /       | |
|  +------------------------------+-----------------------------+ |
|                                 |                               |
|            +--------------------+----------+                    |
|            v                    v          v                    |
|  +-----------------+ +-----------+ +-------------+             |
|  | Pygame DRM      | | Navegador | | Navegador   |             |
|  | (display        | | (misma    | | (LAN/remoto)|             |
|  |  físico)        | | Pi)       | |             |             |
|  | ILI9486 TFT     | |           | |             |             |
|  +-----------------+ +-----------+ +-------------+             |
|       ^ touch                                                  |
|       | XPT2046                                                |
+-------+--------------------------------------------------------+
```

### Principios de diseño

1. **Pi autónoma:** Todo se ejecuta en la Pi. Un navegador = un cliente.
2. **Backend único:** FastAPI es la fuente de verdad. No hay `pi_hmi_server.py` duplicado.
3. **Tipado fuerte:** Pydantic en backend, TypeScript + Zod en frontend = contrato verificable.
4. **Ligero:** SolidJS (sin VDOM), sin Docker en ARMv6, sin Node.js en runtime.
5. **Persistencia:** estado (LED, botón, ajustes de display) en SQLite; el pin GPIO se lee siempre de `devices.yaml`.
6. **Profesional:** documentación exhaustiva, tests, CI, estructura de proyecto estándar.

---

## 2. Stack tecnológico

### 2.1 Backend (Python)

| Componente | Tecnología | Justificación |
|---|---|---|
| Framework HTTP | **FastAPI** | Async nativo, OpenAPI automático, tipado Pydantic |
| Modelos | **Pydantic v2** | Validación estricta, serialización, documentación |
| Hardware GPIO | **gpiozero** | API de alto nivel, soporta BCM2835 |
| Display físico | **Pygame 2.6+** | DRM/KMS nativo, dirty rectangles, touch vía evdev |
| Async | **asyncio** + **anyio** | Concurrencia ligera, WebSocket real-time |
| Servidor | **uvicorn** | ASGI, producción, workers configurables |
| Persistencia | **SQLite** (`data/state.db`) | Estado local sin servidor externo |
| SSH/deploy | **paramiko** | Conexión remota para `/admin/*` |
| Tests | **pytest** + **pytest-asyncio** | Cobertura backend + display |
| Tipado / lint | **mypy** + **ruff** | Verificación estática y estilo |

### 2.2 Frontend web (TypeScript)

| Componente | Tecnología | Justificación |
|---|---|---|
| Framework | **SolidJS** | Señales reactivas, sin VDOM, JSX nativo |
| Bundler | **Vite** | HMR instantáneo, tree-shaking óptimo |
| CSS | **Tailwind CSS v4** | Utility-first, purgado en build |
| Estado | **createSignal** (built-in) | Reactividad fina, sin librerías externas |
| Validación runtime | **Zod** | Esquemas de mensajes WS (`schemas/ws.ts`) |
| Tipado | **TypeScript** (strict) | Contrato tipado con backend |

### 2.3 Display físico (Pygame)

| Componente | Tecnología | Justificación |
|---|---|---|
| Renderizado | **Pygame + DRM/KMS** | Acceso directo a `/dev/dri/card0`, sin X11/Wayland |
| Driver pantalla | `dtoverlay=piscreen,drm` | TinyDRM oficial de Raspberry Pi, dirty rectangles |
| Driver touch | `dtoverlay=ads7846` | XPT2046 vía SPI1 CS1 |
| Optimización | Dirty rectangles | Solo actualiza zonas modificadas |

---

## 3. Estructura del proyecto

```
Rpi_Pantalla_V1/
├── backend/                         # Servidor FastAPI
│   ├── app/
│   │   ├── __init__.py
│   │   ├── _version.py              # Versión leída de VERSION (raíz)
│   │   ├── main.py                  # FastAPI app + lifespan + CORS + static
│   │   ├── config.py                # pydantic-settings (.env)
│   │   ├── api/
│   │   │   ├── __init__.py          # Exporta todos los routers
│   │   │   ├── auth.py              # /api/auth/* (login/logout/status + SessionManager)
│   │   │   ├── deps.py              # require_admin_api_key(_always), loopback exento
│   │   │   ├── hmi.py               # /api/led|button|status|display|settings/display
│   │   │   ├── ws.py                # WebSocket /ws
│   │   │   ├── network.py           # /api/network (GET público, POST protegido)
│   │   │   ├── health.py            # /health, /health/live, /health/ready
│   │   │   ├── ssh.py               # /admin/ssh/* (feature-gated)
│   │   │   └── deploy.py            # /admin/deploy/* (feature-gated)
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── hmi.py               # LedState, ButtonState, DisplayInfo, DisplaySettings,
│   │   │   │                        #   DisplayCommand, SystemStatus
│   │   │   ├── events.py            # ClientMessage, ServerMessage, enums WS
│   │   │   ├── device.py            # DeviceConfig, PinMapping, load_devices()
│   │   │   └── network.py           # NetworkStatus, StaticIpRequest, NetworkResult
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── state_manager.py     # Estado compartido thread-safe + broadcast
│   │   │   ├── ws_hub.py            # Suscripciones por topic + broadcast serializado
│   │   │   ├── gpio_service.py      # Abstracción GPIO (gpiozero) + load_devices()
│   │   │   ├── persistence.py       # Persistencia SQLite asíncrona
│   │   │   ├── network_service.py   # Gestión de red vía NetworkManager (nmcli)
│   │   │   ├── ssh_manager.py       # Driver SSH (Paramiko)
│   │   │   ├── deploy_service.py    # Deploy remoto + escaneo de red
│   │   │   └── systemd_notify.py    # sd_notify: READY/WATCHDOG/STOPPING
│   │   └── hardware/
│   │       └── __init__.py          # Placeholder HAL (GPIO unificado en gpio_service)
│   ├── config/
│   │   └── devices.yaml             # Fuente única de verdad de pines (LED GPIO20/21)
│   ├── tests/                       # pytest (hmi, ws, auth, network, ssh, deploy, ...)
│   ├── pyproject.toml
│   └── requirements.txt
│
├── display/                         # App Pygame (display físico)
│   ├── __init__.py
│   ├── app.py                       # Entry point CLI (--mock, --api-url, --fps...)
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── screen.py                # Gestor de pantalla (DRM/KMS + mock)
│   │   ├── widgets.py               # Widgets: LED, botón, header, status
│   │   ├── theme.py                 # Layout 480x320, colores, fuentes
│   │   └── touch.py                 # Driver táctil (evdev/ADS7846)
│   └── tests/
│
├── frontend/                        # SolidJS + TypeScript + Vite
│   ├── src/
│   │   ├── main.tsx                 # Entry point
│   │   ├── App.tsx                  # Orquestador: auth, WS, navegación de vistas
│   │   ├── components/
│   │   │   ├── LoginScreen.tsx      # Login del panel (cookie HttpOnly)
│   │   │   ├── Header.tsx           # Barra de estado + logout
│   │   │   ├── LedPanel.tsx         # Panel LED
│   │   │   ├── ButtonPanel.tsx      # Panel botones
│   │   │   ├── ConnectionStatus.tsx # Indicador de conexión WS
│   │   │   ├── ConfigPanel.tsx      # Botón de configuración
│   │   │   ├── ConfigScreen.tsx     # Modal de configuración
│   │   │   ├── NetworkConfig.tsx    # Configuración de red
│   │   │   ├── FontSettings.tsx     # Ajustes de fuente/tamaño del display
│   │   │   ├── ScreenTest.tsx       # Prueba de pantalla
│   │   │   └── TouchCalibration.tsx # Calibración táctil
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts      # Gestor de conexión WS
│   │   │   ├── useApi.ts            # Cliente REST (fallback + auth)
│   │   │   ├── useConnectionMonitor.ts # Poll REST como fallback
│   │   │   └── sequenceTracker.ts   # Detección de gaps por topic
│   │   ├── schemas/
│   │   │   └── ws.ts                # Esquemas Zod de mensajes WS
│   │   ├── types/
│   │   │   └── api.ts               # Tipos TS mirror de Pydantic
│   │   └── tests/                   # Vitest + Testing Library
│   ├── index.html
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── package.json
│
├── config/
│   ├── systemd/
│   │   ├── rpi-hmi-backend.service  # Servicio FastAPI (Type=notify + watchdog)
│   │   └── rpi-hmi-display.service  # Servicio Pygame display
│   └── sudoers.d/
│       └── rpi-hmi                  # Regla mínima: pi NOPASSWD /usr/bin/nmcli
│
├── scripts/                         # Despliegue y utilidades
│   ├── deploy.py                    # Deploy unificado (--hmi, --install-service, --verify)
│   ├── deploy_atomic.py             # Deploy atómico con rollback (releases/<version>)
│   ├── start_hmi.sh                 # Arranque del HMI en la Pi
│   └── setup_rpi.sh                 # Configuración inicial de la Pi
│
├── docs/
│   ├── ARCHITECTURE.md              # Este documento
│   ├── SECURITY.md                  # Modelo de amenazas y política de seguridad
│   ├── CONTEXT.md                   # Estado global para agentes IA
│   ├── deploy/
│   │   ├── runbook.md               # Manual operativo de despliegue
│   │   ├── INICIO.md                # Mapa de workstreams
│   │   └── ESTADO_DESPLEGUE.md      # Estado global de despliegue
│   └── deploy/handoffs/             # Documentos de traspaso por fase
│
├── .env.example
├── .gitignore
├── VERSION                          # Versión única del proyecto (0.3.4)
└── README.md
```

---

## 4. Contratos de API

### 4.1 Health check (público)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Diagnóstico completo (`healthy`/`degraded`/`unhealthy`) |
| GET | `/health/live` | Liveness: ¿el proceso está vivo? (siempre 200) |
| GET | `/health/ready` | Readiness: 200 si SQLite responde, 503 si no |

### 4.2 Autenticación (público / AUTH)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/auth/status` | `{security_enabled, authenticated}` (público, sin secretos) |
| POST | `/api/auth/login` | Valida la contraseña del panel (body JSON) y emite cookie `rpi_hmi_session` HttpOnly |
| POST | `/api/auth/logout` | Revoca la sesión y borra la cookie |

### 4.3 HMI — solo lectura (públicos)

| Método | Ruta | Response |
|---|---|---|
| GET | `/api/status` | `SystemStatus` |
| GET | `/api/led` | `LedState` |
| GET | `/api/button` | `ButtonState` |
| GET | `/api/display/info` | `DisplayInfo` (404 si no detectado) |
| GET | `/api/settings/display` | `DisplaySettings` |

### 4.4 HMI — mutadores (PROTECTED cuando la contraseña del panel está activada)

| Método | Ruta | Response |
|---|---|---|
| POST | `/api/led/toggle` | `LedState` |
| POST | `/api/led/on` | `LedState` |
| POST | `/api/led/off` | `LedState` |
| POST | `/api/button/press` | `ButtonState` |
| POST | `/api/button/release` | `ButtonState` |
| POST | `/api/display/command` | `{success, action}` |
| POST | `/api/settings/display` | `DisplaySettings` |

### 4.5 Red (lectura pública, mutación protegida)

| Método | Ruta | Response |
|---|---|---|
| GET | `/api/network` | `NetworkStatus` |
| POST | `/api/network/static` | `NetworkResult` |
| POST | `/api/network/dhcp` | `NetworkResult` |

### 4.6 Administración (feature-gated `ENABLE_ADMIN_API=true`, auth siempre)

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/admin/ssh/connect` | Establecer conexión SSH |
| POST | `/admin/ssh/disconnect` | Cerrar conexión SSH |
| GET | `/admin/ssh/status` | Estado de la conexión |
| POST | `/admin/ssh/execute` | Ejecutar comando remoto (RCE) |
| GET | `/admin/deploy/scan` | Escanear red local |
| POST | `/admin/deploy/setup` | Configurar entorno Python |
| POST | `/admin/deploy/app` | Desplegar archivos de la app |
| GET | `/admin/deploy/diagnostics` | Diagnóstico remoto |
| GET | `/admin/deploy/health` | Salud del backend remoto |
| POST | `/admin/deploy/start` | Iniciar backend remoto |
| POST | `/admin/deploy/stop` | Detener backend remoto |

> Los routers `/admin/*` solo se registran si `ENABLE_ADMIN_API=true` (deshabilitado
> por defecto). Si está deshabilitado, las rutas `/admin/*` responden 404.

### 4.7 Clasificación por autenticación

| Clase | Endpoints | Autenticación |
|---|---|---|
| **PUBLIC** | `/health*`, `GET /api/auth/status`, lecturas HMI/red | Ninguna |
| **AUTH** | `POST /api/auth/login`, `POST /api/auth/logout` | Login valida la contraseña del panel |
| **PROTECTED** | mutadores HMI, `POST /api/settings/display`, `POST /api/network/*`, `WS /ws` | `X-API-Key` **o** cookie de sesión, solo cuando la contraseña del panel está activada; loopback exento |
| **ADMIN** | `/admin/*` | `X-API-Key` **o** cookie de sesión, **siempre** |

Ver `docs/SECURITY.md` para el detalle completo del modelo de amenazas.

---

## 5. Protocolo WebSocket

Conexión: `ws://<host>:8000/ws` · Versión de protocolo: `1.0`

El sobre del mensaje incluye siempre `version`, `type` y (en servidor) `sequence`
(contador global monotónico) y `timestamp`. Los clientes detectan pérdidas por
**topic** (no globalmente), comparando contra el último `sequence` del mismo topic.

### 5.1 Mensajes cliente → servidor

```json
{"version": "1.0", "type": "toggle_led"}
{"version": "1.0", "type": "press_button"}
{"version": "1.0", "type": "release_button"}
{"version": "1.0", "type": "get_status"}
{"version": "1.0", "type": "subscribe", "topics": ["led", "button", "display"]}
{"version": "1.0", "type": "display_command", "action": "screen_test"}
```

Acciones válidas de `display_command`: `screen_test`, `touch_calib`, `network`,
`font`, `security`, `config`, `main`.

### 5.2 Mensajes servidor → cliente

```json
{"version": "1.0", "type": "status_update", "data": { ... }, "sequence": 0, "timestamp": "..."}
{"version": "1.0", "type": "led_changed", "data": {"state": true, "label": "ENCENDIDO", "gpio_pin": 20}, "sequence": 1, "timestamp": "..."}
{"version": "1.0", "type": "button_pressed", "data": {"pressed": true, "press_count": 5}, "sequence": 2, "timestamp": "..."}
{"version": "1.0", "type": "button_released", "data": { ... }, "sequence": 3, "timestamp": "..."}
{"version": "1.0", "type": "display_changed", "data": { ... }, "sequence": 4, "timestamp": "..."}
{"version": "1.0", "type": "display_settings_changed", "data": { ... }, "sequence": 5, "timestamp": "..."}
{"version": "1.0", "type": "display_command", "data": {"action": "..."}, "sequence": 6, "timestamp": "..."}
{"version": "1.0", "type": "error", "data": {"code": "...", "message": "..."}, "timestamp": "..."}
```

> El broadcast se serializa por topic vía `WebSocketHub` (cola FIFO por topic,
> drop-oldest si la cola se llena). El campo `sequence` es `null` en `error` y en
> los `status_update` generados sin asignación de secuencia.

### 5.3 Autenticación del handshake

Cuando la contraseña del panel está activada, las conexiones no-loopback deben
autenticarse antes de `accept()`. Se aceptan, por orden de prioridad:

1. Header `X-API-Key` (scripts/M2M).
2. Cookie de sesión válida (navegador; emitida por `POST /api/auth/login`).
3. Subprotocolo `Sec-WebSocket-Protocol`.

El query param `?token=` **ya no** es una fuente de credencial. Si falla, el
handshake se cierra con close code `4401` (no se llama a `accept()`).
El subprotocolo anunciado por el frontend es `["rpi-hmi"]`.

---

## 6. Modelos de datos (Pydantic ↔ TypeScript/Zod)

```python
# backend/app/models/hmi.py
class LedState(BaseModel):
    state: bool
    label: str  # "ENCENDIDO" | "APAGADO"
    gpio_pin: int = Field(default=0, ge=0, le=27)  # 0 = virtual (sin GPIO físico)

class ButtonState(BaseModel):
    pressed: bool
    press_count: int = Field(default=0, ge=0)

class DisplayInfo(BaseModel):
    connected: bool
    resolution: str  # "480x320"
    driver: str      # "ili9486" | "piscreen"

class DisplaySettings(BaseModel):
    font_family: Literal["dejavu", "liberation"]
    text_size: Literal["small", "medium", "large"]

class SystemStatus(BaseModel):
    led: LedState
    button: ButtonState
    display: DisplayInfo | None
    uptime_seconds: float
    cpu_temp_celsius: float | None
    websocket_clients: int
    timestamp: datetime
```

El LED principal está mapeado a **GPIO 20** y el LED del pulsador a **GPIO 21**
(en `backend/config/devices.yaml`, roles `led` y `button_led`), por lo que
`gpio_pin` de `LedState` es `20`. El pin se resuelve en runtime desde
`devices.yaml` (fuente única de verdad); el valor `default=0` es el fallback
cuando no hay GPIO configurado.

Los equivalentes TypeScript viven en `frontend/src/types/api.ts` y los esquemas de
validación runtime (Zod) de mensajes WS en `frontend/src/schemas/ws.ts`.

---

## 7. Autenticación (flujo del panel web)

La protección del panel web se rige por la **contraseña del panel**, persistida en
SQLite (`password_enabled`) y leída por `security_manager.load()`; está
**desactivada por defecto**. Cuando está activada, los mutadores exigen el header
`X-API-Key` (scripts/M2M) **o** una cookie de sesión válida (navegador). El panel
web usa entonces un flujo de login por **cookie de sesión HttpOnly** (sustituye al
antiguo `VITE_API_KEY`, que ya no existe).

```
Navegador                          Backend FastAPI
   |  1. GET /api/auth/status         |  -> {security_enabled, authenticated}
   |<---------------------------------|
   |  2. (si activada y sin sesión)   |
   |     POST /api/auth/login         |
   |     {"password": "..."}          |
   |<---------------------------------|  -> Set-Cookie: rpi_hmi_session=...
   |  3. fetch REST + WS handshake    |  cookie viaja automáticamente (HttpOnly)
   |     (sin manejar clave en JS)    |
   |  4. POST /api/auth/logout        |  -> revoca sesión + borra cookie
```

- La sesión es **en memoria** (dict `token → expiración`) y se firma con
  HMAC-SHA256 (stdlib) usando una clave derivada de `ADMIN_API_KEY` + secreto
  aleatorio por arranque. Reiniciar el proceso o rotar la clave invalida sesiones.
- Cookie con `HttpOnly`, `SameSite=Strict`; `Secure` solo si HTTPS.
- TTL configurable con `SESSION_TTL_SECONDS` (default `28800` = 8 h).
- Los mutadores aceptan `X-API-Key` (scripts/M2M) **o** cookie de sesión
  (navegador); el loopback (`127.0.0.1`/`::1`/`localhost`) queda exento para que el
  display físico local (Pygame) siga funcionando sin credenciales.

Ver `docs/SECURITY.md` para el modelo completo.

---

## 8. Flujo de datos

### 8.1 Toggle LED desde el display físico (touch)

```
Usuario toca botón en TFT
  -> Pygame detecta touch (evdev) en display/ui/touch.py
  -> display/app.py POST http://localhost:8000/api/led/toggle (loopback exento)
  -> FastAPI actualiza StateManager (thread-safe)
  -> StateManager persiste en SQLite y emite WS broadcast led_changed
  -> Pygame recibe WS y redibuja
```

### 8.2 Toggle LED desde el navegador remoto

```
Usuario hace clic en botón web
  -> SolidJS <LedPanel> envía WS {"type": "toggle_led", "version": "1.0"}
  -> FastAPI recibe WS, actualiza StateManager
  -> FastAPI emite WS broadcast a TODOS los clientes suscritos
  -> SolidJS actualiza la UI reactivamente (fallback REST cada 5s si cae WS)
  -> Pygame (si conectado) recibe WS y redibuja
```

> El LED principal se mapea a **GPIO 20** y el LED del pulsador a **GPIO 21**.
> Los callbacks `set_updater` y `set_updater_button` de `StateManager` sincronizan
> ambos pines vía `GPIOService` cuando cambia su estado.

---

## 9. Persistencia (SQLite)

- Ruta: `data/state.db` (configurable con `DB_PATH`).
- `StateManager` persiste en segundo plano (tareas asíncronas): estado del LED,
  contador del botón, ajustes de display y un log histórico de eventos.
- En el arranque, `restore_from_db()` restaura el estado desde SQLite aplicando la
  política `STARTUP_POLICY` (`off` | `restore` | `safe`, default `restore`).
- El pin GPIO **nunca** se persiste: se lee siempre de `devices.yaml`.
- En el shutdown, `flush_pending_tasks()` drena las escrituras pendientes antes de
  cerrar la conexión (`close_persistence()`).

---

## 10. Despliegue y systemd

Dos servicios systemd (ver `config/systemd/`):

- **`rpi-hmi-backend.service`** — FastAPI con `Type=notify` + watchdog
  (`WATCHDOG=1` cada ~15 s) vía `systemd_notify.py`. El display depende de
  `/health/ready`.
- **`rpi-hmi-display.service`** — Pygame DRM/KMS, arranca tras el backend.

El despliegue se hace con `scripts/deploy.py` (simple) o `scripts/deploy_atomic.py`
(recomendado: copia a `releases/<version>/`, cambia symlink `current`, valida y
reinicia con rollback). La regla sudoers mínima para `nmcli` está en
`config/sudoers.d/rpi-hmi`. Ver `docs/deploy/runbook.md` para el procedimiento
completo y `docs/deploy/ESTADO_DESPLEGUE.md` para el estado global.

---

## 11. Configuración del display físico

### 11.1 Device Tree Overlays (`/boot/firmware/config.txt`)

```
dtparam=spi=on
dtoverlay=piscreen,drm,speed=24000000
dtoverlay=ads7846,cs=1,penirq=25,penirq_pull=2,speed=1000000,rotate=270,swapxy=0
```

### 11.2 Pygame con DRM/KMS

```python
import os
os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
os.environ["SDL_KMSDRM_DEVICE_INDEX"] = "0"  # /dev/dri/card0

import pygame
pygame.display.init()
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
```

### 11.3 Vista "security" (contraseña del panel)

El overlay de CONFIGURACION del display físico incluye una opción **"Contraseña"**
(`SecuritySettingsView` en `display/ui/widgets.py`, vista `"security"` en
`display/app.py`) que permite:

- Ver el estado de la protección por contraseña (activada/desactivada y de
  fábrica `1234` / personalizada).
- Activar/desactivar la protección (`POST /api/auth/security`).
- Cambiar la contraseña (`POST /api/auth/password`).

La introducción de texto se hace con un **teclado numérico en pantalla**
(0-9 + `BORRAR` + `LIMPIAR`). **Limitación:** desde la pantalla física solo se
pueden introducir contraseñas numéricas; para contraseñas alfanuméricas debe
usarse el panel web. La validación de "mínimo 8 caracteres" y "no activar con
la contraseña de fábrica" se hace en cliente (la capa REST del display pierde el
código de estado HTTP); el backend la refuerza en profundidad (422/409).

---

## 12. Métricas de calidad

| Métrica | Objetivo |
|---|---|
| Tests backend + display (pytest) | 346 passed / 9 skipped (baseline) |
| Tests frontend (Vitest) | 26 passed |
| Tipado | mypy (backend) + TypeScript strict (frontend) |
| Bundle frontend (gzip) | < 50 KB |
| RAM idle | < 100 MB |
| Boot time | < 30 s |
| FPS display | >= 15 fps |

---

## 13. Referencias

- [piscreen overlay + DRM — Raspberry Pi Bookworm](https://github.com/raspberrypi/bookworm-feedback/issues/88)
- [TinyDRM ili9486.c en kernel](https://github.com/raspberrypi/linux/blob/rpi-6.6.y/drivers/gpu/drm/tiny/ili9486.c)
- [SolidJS](https://www.solidjs.com/)
- [Pygame + KMS/DRM guide](https://dontpressthat.wordpress.com/2025/09/20/bookworm-drm/)
- [TC39 Signals proposal](https://github.com/tc39/proposal-signals)
