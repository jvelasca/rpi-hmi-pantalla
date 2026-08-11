# CONTEXT.md — Estado Global del Proyecto RPi HMI

> **Proposito:** Checkpoint para agentes de IA. Leer al inicio de CADA sesion.  
> **Actualizar al final de CADA sesion.** No se debe perder nunca el contexto global.

---

## Ultima sesion

- **Fecha:** 2026-08-11 (16:38 – 17:05)
- **Agente:** Cursor Agent (deepseek-v4-pro)
- **Branch:** main
- **Trabajo actual:** Fase 4 completada. Servicios systemd instalados. HMI arranca automaticamente al boot en la TFT.
  - Siguiente: Fase 5 — GitHub Actions, pre-commit, badges.

## Estado actual

| Componente | Estado | Detalle |
|---|---|---|
| Display fisico | OK | `dtoverlay=piscreen,drm,speed=24000000`. `/dev/fb1` 480x320. `/dev/dri/card0`. |
| Touch | OK | `/dev/input/event0` ADS7846 funcionando. |
| Backend | CORRIENDO (systemd) | FastAPI en :8000. `rpi-hmi-backend.service` enabled. Auto-start al boot. |
| Display App Pygame | CORRIENDO (systemd) | `rpi-hmi-display.service` enabled. DRM/KMS 480x320 en TFT. Auto-start al boot. |
| lightdm (escritorio) | DISABLED | `systemctl disable lightdm`. Ya no interfiere con /dev/dri/card0. |
| Frontend SolidJS | CORRIENDO | http://192.168.88.211:8000/. Servido por FastAPI desde static/. |
| Docs | OK | Swagger en http://192.168.88.211:8000/docs |
| Tests | 103/103 pass | 77 backend + 26 display = 103 tests total |
| Systemd | INSTALADO | `rpi-hmi-backend.service` + `rpi-hmi-display.service` enabled. Auto-boot. |

## Fase 1: COMPLETADA

El backend `backend/app/` esta completamente implementado, testeado y corriendo:

### Estructura
```
backend/
├── app/
│   ├── models/
│   │   ├── hmi.py          # LedState, ButtonState, DisplayInfo, SystemStatus
│   │   ├── events.py       # ClientMessage, ServerMessage, SubscriptionTopic
│   │   └── device.py       # DeviceConfig, DeviceType, PinMapping
│   ├── services/
│   │   ├── state_manager.py # Singleton thread-safe con broadcast WS
│   │   └── gpio_service.py  # Auto-detecta Real vs Mock driver
│   ├── api/
│   │   ├── hmi.py           # REST: /api/led, /api/button, /api/status
│   │   └── ws.py            # WebSocket: /ws con subscripciones
│   ├── config.py            # Pydantic Settings via .env
│   └── main.py              # FastAPI app con lifespan, CORS, static
├── tests/
│   ├── test_hmi.py           # 17 tests (REST endpoints)
│   ├── test_state_manager.py # 14 tests (StateManager)
│   └── test_gpio_service.py  # 8 tests (GPIOService)
├── pyproject.toml
└── requirements.txt
```

### Tests: 77/77 pasan

## Fase 2: COMPLETADA (codigo)

Display app Pygame + DRM/KMS implementada. 26 tests pasan en PC (mock mode).

### Estructura
```
display/
├── __init__.py
├── requirements.txt         # pygame, evdev, requests, websocket-client
├── app.py                   # Entry point CLI, main loop, state sync
├── ui/
│   ├── __init__.py
│   ├── theme.py             # Colores, fuentes, layout (480x320 base)
│   ├── touch.py             # Driver evdev ADS7846 con mapeo rotate=270
│   ├── widgets.py           # LedIndicator, ButtonWidget, HeaderWidget, StatusBar
│   └── screen.py            # Gestor Pygame DRM/KMS + mock mode
└── tests/
    ├── __init__.py
    └── test_ui.py            # 26 tests: touch mapping, widgets, screen, theme
```

### Tests: 26/26 pasan (PC/mock)

### Diseño

- **Comunicacion:** REST (commands) + WebSocket (realtime updates) con backend en :8000
- **Widgets:** LedIndicator (circulo LED + boton toggle), ButtonWidget (circulo + contador), Header, StatusBar
- **Touch:** evdev con mapeo rotate=270 (XPT2046 raw 0-4095 → screen 480x320)
- **Screen:** Auto-detecta DRM/KMS (/dev/dri/card0) vs mock (ventana PC). SDL_VIDEODRIVER=kmsdrm
- **Mock mode:** `--mock` para desarrollo en PC sin display fisico

### Arranque (pendiente de probar en la Pi)

```bash
# Instalar dependencias en la Pi
ssh pi@192.168.88.211 "source /home/pi/rpi_hmi/venv/bin/activate && pip install pygame evdev requests websocket-client"

# Ejecutar display app (con backend ya corriendo)
ssh pi@192.168.88.211 "cd /home/pi/rpi_hmi && PYTHONPATH=/home/pi/rpi_hmi /home/pi/rpi_hmi/venv/bin/python3 display/app.py"

# Modo mock en PC (desarrollo)
python display/app.py --mock
```

### Dependencias nuevas (instalar en venv de la Pi)

```
pygame>=2.6,<3.0
evdev>=1.7,<2.0      # Solo Linux (touch)
requests>=2.31,<3.0  # Ya instalado con FastAPI
websocket-client>=1.8,<2.0
```

## Fase 3: COMPLETADA — Frontend SolidJS + TypeScript + Vite

Frontend web servido directamente por el backend FastAPI desde `backend/app/static/`.

### Estructura
```
frontend/
├── index.html              # Entry point HTML
├── package.json            # Dependencias npm
├── tsconfig.json           # TypeScript config (SolidJS + path aliases)
├── tsconfig.node.json      # TS config para vite.config.ts
├── vite.config.ts          # Vite + SolidJS + Tailwind + proxy a Pi
├── dist/                   # Build de produccion (~10.5 KB gzip)
│   ├── index.html
│   ├── vite.svg
│   └── assets/
│       ├── index-*.js      # 16.68 KB (6.39 KB gzip)
│       └── index-*.css     # 13.80 KB (3.70 KB gzip)
├── public/
│   └── vite.svg
└── src/
    ├── main.tsx            # Entry point SolidJS
    ├── App.tsx             # Orquestador: WS + REST + layout
    ├── vite-env.d.ts
    ├── types/
    │   └── api.ts          # Tipos TypeScript (mirror de Pydantic)
    ├── hooks/
    │   ├── useApi.ts       # REST client con fetch
    │   └── useWebSocket.ts # WS client con reconexion automatica
    ├── components/
    │   ├── LedPanel.tsx    # Panel LED con indicador visual + toggle
    │   ├── ButtonPanel.tsx # Boton circular + contador
    │   ├── Header.tsx      # Barra superior con estado WS
    │   └── ConnectionStatus.tsx # Footer con API status
    └── styles/
        └── index.css       # Tailwind v4 entry
```

### Tecnologias
- **Framework:** SolidJS 1.9+ (~7.6 KB gzip)
- **Bundler:** Vite 6
- **CSS:** Tailwind CSS v4
- **Tipado:** TypeScript 5.7+ (strict mode)
- **Build output:** ~10.5 KB gzip total (muy por debajo del objetivo 50 KB)

### Desarrollo local
```bash
cd frontend/
npm install
npm run dev          # Vite dev server en :5173 con proxy a la Pi
npm run build        # Compilar a dist/
```

### Despliegue
```bash
# Compilar
cd frontend/ && npm run build

# Desplegar a la Pi
python scripts/deploy_frontend.py
```

### API
El frontend se comunica con el backend via:
- **WebSocket** (`/ws`) para actualizaciones en tiempo real
- **REST** (`/api/*`) como fallback cuando WS no esta disponible
- **Vite proxy** en desarrollo redirige `/api` y `/ws` al backend de la Pi

### Leccion aprendida: pygame.freetype en ARMv6

El build de pygame 2.6.1 en piwheels para ARMv6 **no incluye el modulo `pygame.freetype`**.
La display app usa `pygame.font` como fallback automatico. El codigo detecta la disponibilidad
de freetype en tiempo de importacion y adapta la API (render_to vs render+blit, get_rect).

### Leccion aprendida: piwheels en ARMv6

`pydantic-core` es el unico paquete con compilacion nativa. piwheels tiene wheels pre-compilados
(`pydantic_core-2.46.4-cp311-cp311-linux_armv6l.whl`) pero pip los descarta por inconsistencia
de nombre (`pydantic-core` vs `pydantic_core`). Solucion: descargar el wheel manualmente con
wget e instalarlo con `pip install <wheel>.whl` ANTES de instalar el resto.

### Arranque de la HMI

```bash
# Opcion 1: Systemd (auto-boot) — la HMI arranca sola al encender la Pi
# (Ya instalado. lightdm deshabilitado.)

# Opcion 2: Manual via SSH
python scripts/deploy.py --hmi
# Detiene lightdm, libera DRM, lanza la HMI en la TFT

# Opcion 3: Script en la Pi
ssh pi@192.168.88.211
cd /home/pi/rpi_hmi
sudo ./scripts/start_hmi.sh

# Opcion 4: Mock en PC (desarrollo)
python display/app.py --mock --debug
# O simplemente python display/app.py (auto-detecta Windows/Mac y activa mock)

# Opcion 5: Mock en PC conectado al backend de la Pi
python display/app.py --mock --api-url http://192.168.88.211:8000 --debug
```

## Decisiones tomadas

1. **Aprobado por el usuario:** Usar `piscreen,drm` (overlay oficial de Raspberry Pi) en lugar del overlay custom.
2. **Aprobado por el usuario:** SolidJS como framework frontend (~7.6KB, el mas ligero y rapido).
3. **Aprobado por el usuario:** Pygame con DRM/KMS para el display fisico.
4. **Aprobado por el usuario:** Eliminar `pi_hmi_server.py`. Unificar todo en FastAPI backend.
5. **Aprobado por el usuario:** Pi autonoma como servidor unico.
6. **Aprobado por el usuario:** Documentacion exhaustiva. `docs/CONTEXT.md` como protocolo anti-perdida de contexto.

## Configuracion activa

```env
RPI_HOST=192.168.88.211
RPI_USER=pi
RPI_PASSWORD=RaspberryB+2026!
RPI_PORT=22
BACKEND_PORT=8000
```

**Overlay actual en `/boot/firmware/config.txt`:**
```
dtparam=spi=on
dtoverlay=ads7846,cs=1,penirq=25,penirq_pull=2,speed=1000000,rotate=270,swapxy=0
dtoverlay=piscreen,drm,speed=24000000
```

## Archivos creados/modificados (esta sesion)

- `display/__init__.py` — NUEVO
- `display/requirements.txt` — NUEVO
- `display/app.py` — NUEVO (entry point, main loop, REST+WS sync)
- `display/ui/__init__.py` — NUEVO
- `display/ui/theme.py` — NUEVO (colores, layout 480x320)
- `display/ui/touch.py` — NUEVO (evdev ADS7846, rotate=270 mapping)
- `display/ui/widgets.py` — NUEVO (LedIndicator, ButtonWidget, Header, StatusBar)
- `display/ui/screen.py` — NUEVO (Pygame DRM/KMS + mock mode)
- `display/tests/__init__.py` — NUEVO
- `display/tests/test_ui.py` — NUEVO (26 tests)
- `docs/CONTEXT.md` — ACTUALIZADO

## Estructura de la Pi

```
/home/pi/rpi_hmi/
├── venv/                     # Python venv (pydantic 2.13.4 + FastAPI 0.141.1)
├── backend/                  # Backend FastAPI
│   └── app/
│       ├── models/  # LedState, ButtonState, SystemStatus, etc.
│       ├── services/ # StateManager + GPIOService
│       ├── api/      # REST + WebSocket
│       ├── main.py   # FastAPI app
│       └── config.py # Settings
├── display/                  # NUEVO — Display app Pygame DRM
│   ├── app.py       # Entry point
│   └── ui/          # touch, widgets, screen, theme
├── pi_hmi_server.py  # LEGACY - detenido
├── fb_ui.py          # LEGACY - detenido
└── fb_test.py        # Test framebuffer
```

## Tareas pendientes

- [x] **Fase 1:** Backend refactorizado, 77 tests pasan, corriendo en la Pi
- [x] **Fase 1.1:** Instalar servicios systemd en la Pi
- [x] **Fase 2:** Implementar `display/` con Pygame + DRM/KMS + Touch
- [x] **Fase 2.1:** Desplegar display app en la Pi, instalar deps, verificar imports
- [x] **Fase 2.2:** Probar display/app.py en la TFT de la Pi (CONFIRMADO — DRM/KMS 480x320)
- [x] **Fase 3:** Crear `frontend/` con SolidJS + TypeScript + Vite (COMPLETADO + DESPLEGADO)
- [x] **Fase 4:** Servicios systemd instalados y enabled. HMI auto-boot en la TFT.
- [ ] **Fase 5:** GitHub Actions, pre-commit, badges

### Archivos creados/modificados (fase 3)
- `frontend/` — Proyecto completo SolidJS + Vite + Tailwind (COMPLETADO + DESPLEGADO)
- `scripts/deploy_frontend.py` — Deploy SFTP del build frontend a la Pi
- `scripts/deploy.py` — Script unificado: deploy, deps, --hmi, --install-service
- `scripts/start_hmi.sh` — Script en la Pi: stop lightdm, unbind vtcon1, launch HMI
- `config/systemd/rpi-hmi-display.service` — Auto-boot con Conflicts=lightdm
- `docs/CONTEXT.md` — Actualizado

## Versiones instaladas en la Pi (venv)

```
fastapi         0.141.1
uvicorn         0.52.1
pydantic        2.13.4
pydantic-core   2.46.4   ← wheel ARMv6 manual de piwheels
pydantic-settings 2.15.0
starlette       1.6.0
websockets      17.0.1
anyio           4.14.2
pygame          2.6.1     ← display app (sin freetype en ARMv6)
evdev           1.9.3     ← touch driver
websocket-client 1.9.0    ← WS en display app
requests        2.34.2    ← REST en display app
```

## Procedimiento de instalacion en Pi (si hay que recrear el venv)

```bash
# 1. Crear venv
python3 -m venv /home/pi/rpi_hmi/venv --clear
source /home/pi/rpi_hmi/venv/bin/activate

# 2. Descargar pydantic-core wheel manualmente (pip lo descarta por bug de nombre)
wget -q -O /tmp/pydantic_core.whl \
  'https://www.piwheels.org/simple/pydantic-core/pydantic_core-2.46.4-cp311-cp311-linux_armv6l.whl'
cp /tmp/pydantic_core.whl /tmp/pydantic_core-2.46.4-cp311-cp311-linux_armv6l.whl
pip install --no-deps /tmp/pydantic_core-2.46.4-cp311-cp311-linux_armv6l.whl

# 3. Instalar el resto (pydantic-core ya esta)
pip install fastapi uvicorn pydantic pydantic-settings websockets

# 4. Dependencias display app (Fase 2)
pip install pygame evdev requests websocket-client
```
