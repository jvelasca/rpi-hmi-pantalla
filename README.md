# Raspberry HMI — Panel de Control Táctil

[![GitHub](https://img.shields.io/badge/github-jvelasca%2Frpi--hmi--pantalla-blue?logo=github)](https://github.com/jvelasca/rpi-hmi-pantalla)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![SolidJS](https://img.shields.io/badge/SolidJS-1.9-blue?logo=solid)](https://www.solidjs.com/)
[![Tests](https://img.shields.io/badge/tests-332%20pytest%20%2B%2026%20vitest-green)]()
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/jvelasca/rpi-hmi-pantalla/blob/main/LICENSE)

Plataforma HMI (Human-Machine Interface) para Raspberry Pi con pantalla táctil 3.5",
botón virtual y LED interactivo. Comunicación en tiempo real vía WebSocket.

**Panel web:** [http://&lt;RASPBERRY_IP&gt;:8000](http://&lt;RASPBERRY_IP&gt;:8000)  
**API docs:** [http://&lt;RASPBERRY_IP&gt;:8000/docs](http://&lt;RASPBERRY_IP&gt;:8000/docs)

---

## Hardware

| Componente | Detalle |
|------------|---------|
| **Placa** | Raspberry Pi Model B+ Rev 1.2 (BCM2835, ARMv6, 512MB RAM) |
| **Pantalla** | 3.5" SPI TFT 480×320 ILI9486 + táctil XPT2046 |
| **LED** | **Virtual** — sin GPIO físico (`backend/config/devices.yaml` usa `pin: null`, `virtual: true`) |
| **Touch IRQ** | GPIO 17 (`TP_IRQ`/pendown del XPT2046) — **NO** conectar un LED aquí |
| **Red** | Ethernet — IP estática `<RASPBERRY_IP>` |
| **OS** | Raspberry Pi OS Bookworm Lite 32-bit, kernel 6.12 |

> **Aviso:** el LED es **virtual** (solo se muestra en pantalla y web). No
> conectes un LED físico a **GPIO 17**: ese pin es la interrupción del panel
> táctil (XPT2046 `TP_IRQ`/pendown) y un LED ahí interferiría con el touch.

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                    Raspberry Pi &lt;RASPBERRY_IP&gt;                   │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐ │
│  │  TFT 3.5" ILI9486    │  │  FastAPI Backend :8000           │ │
│  │  Pygame DRM/KMS      │  │  ├─ REST API /api/*              │ │
│  │  display/app.py      │  │  ├─ WebSocket /ws                │ │
│  │  rpi-hmi-display     │  │  ├─ SolidJS Frontend (static)    │ │
│  │  (systemd auto-boot)  │  │  └─ Swagger /docs               │ │
│  │                       │  │  rpi-hmi-backend (systemd)       │ │
│  └──────────┬───────────┘  └──────────────────────────────────┘ │
│             │                         │                          │
│  ┌──────────┴─────────────────────────┴──────────────────────┐ │
│  │                 ESTADO COMPARTIDO                          │ │
│  │  • LED state (bool) + label                               │ │
│  │  • Button press count (int)                               │ │
│  │  • WebSocket clients (broadcast)                          │ │
│  └──────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

         Navegador (LAN)              VS Code (PC)
    http://&lt;RASPBERRY_IP&gt;:8000    Python display/app.py --mock
```

### Componentes

| Componente | Tecnología | Descripción |
|---|---|---|
| **Backend** | FastAPI + Pydantic v2 | REST + WebSocket + GPIO |
| **Display TFT** | Pygame + DRM/KMS | Render directo 480x320 en ILI9486 |
| **Touch** | evdev | Driver ADS7846/XPT2046 |
| **Frontend Web** | SolidJS + TypeScript + Vite + Tailwind v4 | Panel de control < 11 KB gzip |
| **Systemd** | 2 services | Auto-boot backend + display (lightdm disabled) |
| **Tests** | Pytest + Vitest | 332 tests (backend+display) + 26 frontend |

---

## API REST

Todos los endpoints disponibles en `http://&lt;RASPBERRY_IP&gt;:8000`:

### LED

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/led` | Estado actual del LED |
| `POST` | `/api/led/toggle` | Alternar LED (ON ↔ OFF) |
| `POST` | `/api/led/on` | Encender LED |
| `POST` | `/api/led/off` | Apagar LED |

### Botón

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/button` | Estado del botón y contador |
| `POST` | `/api/button/press` | Registrar pulsación |

### Sistema

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/status` | Estado completo (LED + botón + WS clients) |
| `GET` | `/health` | Health check completo |
| `GET` | `/health/live` | Liveness probe (siempre 200) |
| `GET` | `/health/ready` | Readiness probe (200 si BD OK) |

### WebSocket

| Protocolo | Dirección | Descripción |
|-----------|-----------|-------------|
| `WS` | `ws://<RASPBERRY_IP>:8000/ws` | Canal bidireccional JSON |

Mensajes **Servidor → Cliente:**
```json
{"type": "led_changed", "data": {"state": true, "label": "ENCENDIDO"}}
{"type": "button_pressed", "data": {"press_count": 5}}
{"type": "status_update", "data": { ... }}
```

---

## Quick Start

### En la Raspberry Pi (auto-boot)

Los servicios systemd arrancan automáticamente al encender la Pi:

```bash
# Verificar que todo corre
ssh pi@&lt;RASPBERRY_IP&gt;
systemctl status rpi-hmi-backend rpi-hmi-display
```

### Desarrollo en PC

```bash
# Backend (requiere Python 3.11+)
pip install fastapi uvicorn pydantic pydantic-settings websockets httpx pytest
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Display (mock mode, necesita pygame)
pip install pygame
python display/app.py --mock --api-url http://&lt;RASPBERRY_IP&gt;:8000

# Frontend (dev server)
cd frontend && npm install && npm run dev
```

### Despliegue a la Pi

```bash
# Deploy completo y arranque de HMI en TFT
python scripts/deploy.py --hmi

# Instalar servicios systemd (auto-boot)
python scripts/deploy.py --install-service

# Solo verificar estado
python scripts/deploy.py --verify
```

---

## Configuración de desarrollo

El frontend (Vite) resuelve la URL del backend mediante la variable de entorno
`VITE_API_URL` (por defecto `http://localhost:8000`). En desarrollo, el proxy de
Vite (`frontend/vite.config.ts`) reenvía `/api`, `/ws` y `/health` a esa URL.
Copia `frontend/.env.example` a `frontend/.env` para sobrescribirla:

```bash
# frontend/.env
VITE_API_URL=http://localhost:8000
```

Si el backend corre en la Raspberry Pi (no en localhost), apunta `VITE_API_URL`
a la IP de la Pi (p. ej. `http://<IP_DE_LA_PI>:8000`). En producción el frontend
se sirve desde el propio backend (mismo origen), por lo que no se necesita.

---

## Estructura del proyecto

```
rpi-hmi-pantalla/
├── backend/                     # FastAPI Backend
│   ├── app/
│   │   ├── main.py              # FastAPI app (lifespan, CORS, static)
│   │   ├── config.py            # pydantic-settings
│   │   ├── api/hmi.py           # REST: /api/led, /api/button, /api/status
│   │   ├── api/ws.py            # WebSocket: /ws con subscripciones
│   │   ├── models/              # Pydantic v2: LedState, ButtonState, etc.
│   │   ├── services/            # StateManager, GPIOService (real/mock)
│   │   └── (frontend servido desde frontend/dist/) 
│   ├── tests/                   # pytest
│   └── requirements.txt
│
├── display/                     # Pygame DRM/KMS Display App
│   ├── app.py                   # Entry point CLI, main loop
│   ├── ui/
│   │   ├── screen.py            # DRM/KMS + mock mode
│   │   ├── touch.py             # evdev ADS7846 (rotate=270)
│   │   ├── widgets.py           # LedIndicator, ButtonWidget, Header, StatusBar
│   │   └── theme.py             # 480x320 layout, colores
│   ├── tests/                   # pytest
│   └── requirements.txt
│
├── frontend/                    # SolidJS + TypeScript + Vite
│   ├── src/
│   │   ├── App.tsx              # Orquestador WS + REST
│   │   ├── components/          # LedPanel, ButtonPanel, Header, ConnectionStatus
│   │   ├── hooks/               # useApi, useWebSocket
│   │   └── types/api.ts         # Tipos mirror de Pydantic
│   └── vite.config.ts
│
├── config/systemd/              # Servicios systemd
│   ├── rpi-hmi-backend.service  # FastAPI auto-boot
│   └── rpi-hmi-display.service  # Pygame DRM auto-boot
│
├── scripts/                     # Despliegue y utilidades
│   ├── deploy.py                # Script unificado: deploy, --hmi, --install-service
│   ├── deploy_frontend.py       # Deploy SFTP del frontend
│   └── start_hmi.sh             # Script en la Pi
│
└── docs/
    ├── CONTEXT.md               # Estado global del proyecto
    └── ARCHITECTURE.md          # Documentación de arquitectura
```

---

## Tests

Estado verificado por CI (2026-08-20): **332 tests** (pytest, backend + display) y **26 tests** de frontend (Vitest).

```bash
# Suite completa (backend + display)
pytest backend/tests/ display/tests/

# Backend
pytest backend/tests/ -q

# Display — mock mode, sin GPU
pytest display/tests/ -q

# Frontend (Vitest) + build
cd frontend && npm run test && npm run build
```

Alcanza:
- ✅ Inicio/apagado del backend (lifespan)
- ✅ Concurrencia del StateManager (múltiples hilos)
- ✅ Endpoint WebSocket (protocolo, suscripción, broadcast, desconexión)
- ✅ Persistencia SQLite (rotación event_log, drenado shutdown, edge cases)
- ✅ Validación de modelos Pydantic (DeviceConfig, ClientMessage, ServerMessage)
- ✅ CLI de la app display (`--mock`, `--api-url`, `--debug`, `--fps`)
- ✅ Sincronización de estado display ↔ backend
- ✅ Detección de dispositivo touch (sin fallback a event0)
- ✅ Deploy con manejo de errores (archivos faltantes, backend caído)
- ✅ Integración completa REST ↔ WebSocket ↔ Admin API
- ✅ Seguridad (CORS, API key, 401/404/500)

---

## Licencia

MIT

## Autores

Desarrollado con GitHub Copilot y DeepSeek-V4-Pro
