# RPi HMI — Arquitectura del Sistema (v0.3.0)

> **Estado:** Plan para implementacion  
> **Ultima actualizacion:** 2026-08-11  
> **Hardware:** Raspberry Pi B+ V1.2 (BCM2835 ARMv6, 512MB RAM)  
> **Display:** 3.5" ILI9486 480x320 SPI + XPT2046 Touch  

---

## 1. Vision General

Sistema HMI embebido autonomo para Raspberry Pi con doble interfaz de usuario:

| Interfaz | Tecnologia | Proposito |
|---|---|---|
| **Display fisico** (3.5" TFT) | Pygame + DRM/KMS | Panel de control tactil local |
| **Frontend web** | SolidJS + TypeScript | Control remoto desde navegador |

Ambos se comunican con un **unico backend FastAPI** que abstrae el hardware (GPIO, SPI, I2C) y gestiona el estado del sistema.

```
+------------------ Raspberry Pi (autonoma) ---------------------+
|                                                                  |
|  +------------------------------------------------------------+ |
|  |           Backend FastAPI (Python 3.11 + tipado)           | |
|  |                                                            | |
|  |  * REST API  (/:8000/api/*)          Pydantic v2 models   | |
|  |  * WebSocket (/:8000/ws)             Estado en tiempo real | |
|  |  * HAL       (gpiozero)              GPIO, SPI, I2C        | |
|  |  * Static    (SolidJS compilado)     Servido desde /static | |
|  +------------------------------+-----------------------------+ |
|                                 |                               |
|            +--------------------+----------+                    |
|            v                    v          v                    |
|  +-----------------+ +-----------+ +-------------+             |
|  | Pygame DRM      | | Navegador | | Navegador   |             |
|  | (display        | | (misma    | | (LAN/remoto)|             |
|  |  fisico)        | | Pi)       | |             |             |
|  | ILI9486 TFT     | |           | |             |             |
|  +-----------------+ +-----------+ +-------------+             |
|       ^ touch                                                  |
|       | XPT2046                                                |
+-------+--------------------------------------------------------+
```

### Principios de Diseno

1. **Pi autonoma:** Todo se ejecuta en la Pi. Un navegador = un cliente.
2. **Backend unico:** FastAPI es la fuente de verdad. No hay `pi_hmi_server.py` duplicado.
3. **Tipado fuerte:** Pydantic en backend, TypeScript en frontend = contrato verificable.
4. **Ligero:** SolidJS (~7.6KB gzip), sin Docker en ARMv6, sin Node.js en runtime.
5. **Profesional:** Documentacion exhaustiva, tests, CI, estructura de proyecto estandar.
6. **Preservacion de contexto:** `docs/CONTEXT.md` como checkpoint para agentes de IA.

---

## 2. Stack Tecnologico

### 2.1 Backend (Python)

| Componente | Tecnologia | Justificacion |
|---|---|---|
| Framework HTTP | **FastAPI 0.115+** | Async nativo, OpenAPI automatico, tipado Pydantic |
| Modelos | **Pydantic v2** | Validacion estricta, serializacion, documentacion |
| Hardware GPIO | **gpiozero** | API de alto nivel, soporta BCM2835 |
| Display fisico | **Pygame 2.6+** | DRM/KMS nativo, dirty rectangles, touch via evdev |
| Async | **asyncio** + **anyio** | Concurrencia ligera, WebSocket real-time |
| Servidor | **uvicorn** | ASGI, produccion, workers configurables |
| Tests | **pytest** + **pytest-asyncio** | Cobertura >= 80% |
| Tipado | **mypy** (strict mode) | Verificacion estatica total |
| Linting | **ruff** | Rapido, reemplaza flake8+isort+black |

### 2.2 Frontend Web (TypeScript)

| Componente | Tecnologia | Tamano (gzip) | Justificacion |
|---|---|---|---|
| Framework | **SolidJS 1.9+** | ~7.6 KB | El mas rapido, sin VDOM, JSX nativo |
| Bundler | **Vite 6** | — | HMR instantaneo, tree-shaking optimo |
| CSS | **Tailwind CSS v4** | ~3 KB | Utility-first, purgado en build |
| Estado | **createSignal** (built-in) | 0 KB extra | Reactividad fina, sin librerias externas |
| Tipado | **TypeScript 5.x** (strict) | — | Contrato tipado con backend |

### 2.3 Display Fisico (Pygame)

| Componente | Tecnologia | Justificacion |
|---|---|---|
| Renderizado | **Pygame + DRM/KMS** | Acceso directo a /dev/dri/card0, sin X11/Wayland |
| Driver pantalla | **dtoverlay=piscreen,drm,speed=24000000** | TinyDRM oficial de Raspberry Pi, dirty rectangles |
| Driver touch | **dtoverlay=ads7846** | XPT2046 via SPI1 CS1 |
| Optimizacion | Dirty rectangles | Solo actualiza zonas modificadas (10-25 FPS efectivos) |
| Fuentes | Pygame freetype | Renderizado escalable de fuentes TTF |

---

## 3. Estructura del Proyecto

```
Rpi_Pantalla_V1/
├── backend/                         # Servidor FastAPI
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app + lifespan events
│   │   ├── config.py                # Pydantic Settings (.env)
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py            # Router principal (/api/*)
│   │   │   ├── hmi.py              # Endpoints HMI (LED, button)
│   │   │   ├── deploy.py           # Deploy remoto
│   │   │   └── ws.py               # WebSocket handler
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── state_manager.py     # Estado compartido (singleton)
│   │   │   ├── display_service.py   # Pygame DRM display manager
│   │   │   └── gpio_service.py      # Abstraction GPIO (gpiozero)
│   │   ├── hardware/
│   │   │   ├── __init__.py
│   │   │   ├── hal.py              # Hardware Abstraction Layer
│   │   │   └── devices.py          # Registro de dispositivos
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── hmi.py              # Pydantic models: LED, Button
│   │   │   ├── events.py           # WebSocket message schemas
│   │   │   └── device.py           # Device configuration schemas
│   │   └── static/                  # Frontend compilado (Vite build)
│   ├── tests/
│   │   ├── test_hmi.py
│   │   ├── test_state_manager.py
│   │   ├── test_display_service.py
│   │   ├── test_gpio_service.py
│   │   └── test_ws.py
│   ├── pyproject.toml              # Project metadata + tool config
│   └── requirements.txt
│
├── frontend/                        # SolidJS + TypeScript
│   ├── src/
│   │   ├── main.tsx                 # Entry point
│   │   ├── App.tsx                  # Root component
│   │   ├── components/
│   │   │   ├── LedPanel.tsx         # Panel LED (local + remoto)
│   │   │   ├── ButtonPanel.tsx      # Panel botones
│   │   │   ├── Header.tsx           # Barra de estado
│   │   │   └── ConnectionStatus.tsx # Indicador WS
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts      # WS connection manager
│   │   │   └── useApi.ts            # REST fallback
│   │   ├── store/
│   │   │   └── state.ts             # Global reactive state
│   │   ├── types/
│   │   │   └── api.ts               # TS types (matching Pydantic)
│   │   └── styles/
│   │       └── index.css            # Tailwind + custom
│   ├── public/
│   ├── index.html
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── package.json
│
├── display/                         # App Pygame (display fisico)
│   ├── __init__.py
│   ├── app.py                       # Punto de entrada display
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── screen.py               # Gestor de pantalla (DRM)
│   │   ├── widgets.py              # Widgets: boton, LED, slider
│   │   ├── theme.py                # Colores, fuentes, estilos
│   │   └── touch.py                # Driver tactil (evdev)
│   └── tests/
│       └── test_ui.py
│
├── config/
│   ├── devices.yaml                 # Registro de hardware
│   └── systemd/
│       ├── rpi-hmi-backend.service  # Servicio FastAPI
│       └── rpi-hmi-display.service  # Servicio Pygame display
│
├── scripts/
│   ├── deploy.sh                    # Deploy a la Pi
│   ├── setup_pi.sh                  # Configuracion inicial
│   └── build_frontend.sh           # Compilar frontend
│
├── docs/
│   ├── ARCHITECTURE.md              # Este documento
│   ├── CONTEXT.md                   # Contexto para agentes IA
│   ├── API.md                       # Referencia de API
│   ├── HARDWARE.md                  # Cableado y pines
│   └── DEVELOPMENT.md              # Guia de desarrollo
│
├── .env.example
├── .gitignore
├── Makefile                         # Tareas comunes
└── README.md
```

---

## 4. Contratos de API

### 4.1 REST Endpoints

| Metodo | Ruta | Response | Descripcion |
|---|---|---|---|
| GET | /health | {"status":"ok"} | Health check |
| GET | /api/status | SystemStatus | Estado completo |
| GET | /api/led | LedState | Estado del LED |
| POST | /api/led/toggle | LedState | Alternar LED |
| POST | /api/led/on | LedState | Encender LED |
| POST | /api/led/off | LedState | Apagar LED |
| GET | /api/button | ButtonState | Estado del boton |
| POST | /api/button/press | ButtonState | Presionar boton |
| GET | /api/display/info | DisplayInfo | Info del display fisico |
| GET | /api/device/list | list[DeviceInfo] | Dispositivos registrados |

### 4.2 WebSocket Protocol

Conexion: `ws://<host>:8000/ws`

**Mensajes Cliente -> Servidor:**
```json
{"type": "toggle_led"}
{"type": "press_button"}
{"type": "release_button"}
{"type": "get_status"}
{"type": "subscribe", "topics": ["led", "button", "display"]}
```

**Mensajes Servidor -> Cliente:**
```json
{"type": "status_update", "data": {"led": {"state": true}, "button": {"count": 5}}}
{"type": "led_changed", "data": {"state": true, "timestamp": 1234567890}}
{"type": "button_pressed", "data": {"timestamp": 1234567890}}
```

### 4.3 Modelos Pydantic (backend) = TypeScript (frontend)

```python
# backend/app/models/hmi.py
from pydantic import BaseModel, Field
from datetime import datetime

class LedState(BaseModel):
    state: bool = Field(description="True = encendido")
    label: str = Field(description="ENCENDIDO | APAGADO")
    gpio_pin: int = Field(default=17, ge=0, le=27)

class ButtonState(BaseModel):
    pressed: bool
    press_count: int = Field(ge=0)

class DisplayInfo(BaseModel):
    connected: bool
    resolution: str = Field(pattern=r"\d+x\d+")
    driver: str

class SystemStatus(BaseModel):
    led: LedState
    button: ButtonState
    display: DisplayInfo | None
    uptime_seconds: float
    cpu_temp_celsius: float | None
    websocket_clients: int = Field(ge=0)
    timestamp: datetime
```

```typescript
// frontend/src/types/api.ts
export interface LedState {
  state: boolean;
  label: string;
  gpio_pin: number;
}

export interface ButtonState {
  pressed: boolean;
  press_count: number;
}

export interface SystemStatus {
  led: LedState;
  button: ButtonState;
  display: DisplayInfo | null;
  uptime_seconds: number;
  cpu_temp_celsius: number | null;
  websocket_clients: number;
  timestamp: string;
}
```

---

## 5. Flujo de Datos

### 5.1 Toggle LED desde Display Fisico (Touch)

```
Usuario toca boton en TFT
  -> Pygame detecta touch (evdev)
  -> display/ui/touch.py traduce coordenadas a widget
  -> display/app.py POST http://localhost:8000/api/led/toggle
  -> FastAPI actualiza StateManager
  -> FastAPI emite WS broadcast: {"type": "led_changed", ...}
  -> Pygame recibe WS y redibuja
  -> GPIO 17 se actualiza via gpiozero
```

### 5.2 Toggle LED desde Navegador Remoto

```
Usuario hace clic en boton web
  -> SolidJS <LedPanel> llama a toggleLed()
  -> WebSocket envia: {"type": "toggle_led"}
  -> FastAPI recibe WS, actualiza StateManager
  -> FastAPI emite WS broadcast a TODOS los clientes
  -> SolidJS actualiza UI reactivamente
  -> Pygame (si conectado) recibe WS y redibuja
  -> GPIO 17 se actualiza via gpiozero
```

---

## 6. Configuracion del Display Fisico

### 6.1 Device Tree Overlays (/boot/firmware/config.txt)

```
dtparam=spi=on
dtoverlay=piscreen,drm,speed=24000000
dtoverlay=ads7846,cs=1,penirq=25,penirq_pull=2,speed=1000000,rotate=270,swapxy=0
```

### 6.2 Pygame con DRM/KMS

```python
import os
os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
os.environ["SDL_KMSDRM_DEVICE_INDEX"] = "0"  # /dev/dri/card0

import pygame
pygame.display.init()
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
```

**Ventajas sobre /dev/fb1:** Dirty rectangles automatico (~20 FPS vs ~5 FPS), sin conflicto con consola.

---

## 7. Estrategia de Contexto para Agentes IA

### CONTEXT.md

Archivo obligatorio que todo agente IA debe leer. Contiene:

- Ultima sesion (fecha, agente, branch, commit)
- Estado actual (display, backend, frontend, tests)
- Decisiones tomadas con justificaciones
- Tareas pendientes
- Configuracion activa (IP, puertos, overlays)
- Archivos modificados en la ultima sesion

### Protocolo de Traspaso

Cuando el chat se satura:
1. El agente actualiza `docs/CONTEXT.md`
2. El agente informa al usuario que abra un nuevo chat
3. El usuario copia `CONTEXT.md` como prompt inicial
4. El nuevo agente lee el contexto y continua donde se quedo

---

## 8. Plan de Implementacion

| Fase | Nombre | Entregables |
|---|---|---|
| 1 | Refactor Backend | StateManager, GPIOService, modelos Pydantic, tests |
| 2 | Display Pygame DRM | piscreen overlay, widgets (LED, Button), integracion WS |
| 3 | Frontend SolidJS | Componentes tipados, WebSocket client, build optimizado |
| 4 | Integracion | Servicios systemd, setup_pi.sh, Makefile, docs completas |
| 5 | CI/CD GitHub | Actions, pre-commit, badges, changelog |

---

## 9. Metricas de Calidad

| Metrica | Objetivo |
|---|---|
| Tests backend | >= 80% |
| Tests frontend | >= 70% |
| Tipado | mypy strict + TS strict |
| Bundle frontend (gzip) | < 50 KB |
| RAM idle | < 100 MB |
| Boot time | < 30s |
| FPS display | >= 15 fps |
| Documentacion | 5 archivos minimos |

---

## 10. Notas Tecnicas

### Por que SolidJS?

| Framework | Bundle | Modelo | Velocidad en ARMv6 |
|---|---|---|---|
| React 19 | ~45 KB | Virtual DOM | Lento |
| Vue 3.5 | ~38 KB | VDOM + Proxy | Medio |
| Svelte 5 | ~15 KB | Compilado | Rapido |
| **SolidJS 1.9** | **~7.6 KB** | **Signals** | **El mas rapido** |

Menor bundle, mejor rendimiento, signals como estandar TC39 futuro.

### Por que Pygame + DRM?

| Metodo | FPS | Dirty rects | Mantenibilidad |
|---|---|---|---|
| /dev/fb1 mmap | 3-5 | Manual | Baja |
| **Pygame + DRM/KMS** | **15-20** | **Automatico** | **Alta** |
| Qt/QML | 10-15 | Si | Media |
| LVGL (C) | 20-25 | Si | Baja |

Pygame + DRM es el sweet spot para Python en Pi.

### Por que no Docker?

- ARMv6 sin soporte practico en Docker Hub
- +50-100MB RAM de overhead (critico en 512MB total)
- systemd es nativo y suficiente para 2 servicios

---

## 11. Referencias

- [piscreen overlay + DRM — Raspberry Pi Bookworm](https://github.com/raspberrypi/bookworm-feedback/issues/88)
- [TinyDRM ili9486.c en kernel](https://github.com/raspberrypi/linux/blob/rpi-6.6.y/drivers/gpu/drm/tiny/ili9486.c)
- [SolidJS state in 2026](https://listiak.dev/blog/the-state-of-solid-js-in-2026-signals-performance-and-growing-influence)
- [Framework comparison — real world apps](https://github.com/naufalafif/realworld-js-framework-comparison)
- [Pygame + KMS/DRM guide](https://dontpressthat.wordpress.com/2025/09/20/bookworm-drm/)
- [TC39 Signals proposal](https://github.com/tc39/proposal-signals)
