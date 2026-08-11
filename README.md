# Raspberry HMI — Panel de Control Táctil

Plataforma HMI (Human-Machine Interface) para Raspberry Pi con pantalla táctil 3.5",
botón virtual y LED interactivo. Comunicación en tiempo real vía WebSocket.

**URL de acceso local:** `http://192.168.88.211:8000`
**WebSocket:** `ws://192.168.88.211:8001/ws`

---

## Hardware

| Componente | Detalle |
|------------|---------|
| **Placa** | Raspberry Pi Model B+ Rev 1.2 (BCM2835, ARMv6, 512MB RAM) |
| **Pantalla** | 3.5" SPI TFT 480×320 ILI9486 + táctil XPT2046 |
| **LED** | GPIO 17 (pin físico 11) con resistencia 220Ω |
| **Red** | Ethernet — IP estática `192.168.88.211` |
| **OS** | Raspberry Pi OS Bookworm Lite 32-bit, kernel 6.12 |

---

## Arquitectura

```
┌──────────────────────────────────────────────────┐
│                  FRONTEND (3 capas)               │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ fb_ui.py    │  │ index.html   │  │ API HTTP  │ │
│  │ framebuffer │  │ navegador    │  │ curl/Post │ │
│  │ /dev/fb0    │  │ :8000        │  │ :8000     │ │
│  └──────┬──────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                │                │        │
├─────────┼────────────────┼────────────────┼────────┤
│         ▼                ▼                ▼        │
│  ┌──────────────────────────────────────────────┐  │
│  │          pi_hmi_server.py (:8000)             │  │
│  │  • HTTP REST API (stdlib http.server)         │  │
│  │  • WebSocket (:8001) — asyncio nativo         │  │
│  │  • Sirve index.html desde static/             │  │
│  └──────────────────────┬───────────────────────┘  │
│                         │                          │
│  ┌──────────────────────┴───────────────────────┐  │
│  │          ESTADO COMPARTIDO                    │  │
│  │  • led_state (bool)                           │  │
│  │  • button_press_count (int)                   │  │
│  │  • ws_clients (list)                          │  │
│  └──────────────────────────────────────────────┘  │
│                                                    │
│  ┌──────────────────────────────────────────────┐  │
│  │       BACKEND PC (FastAPI, opcional)          │  │
│  │  backend/app/api/hmi.py                       │  │
│  │  backend/app/services/ssh_manager.py          │  │
│  └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Componentes principales

| Componente | Archivo | Descripción | Puerto |
|------------|---------|-------------|--------|
| **Servidor HMI** | `pi_hmi_server.py` | HTTP + WebSocket standalone (stdlib) | `:8000` HTTP, `:8001` WS |
| **UI Framebuffer** | `fb_ui.py` | Render directo en /dev/fb0 con soporte táctil | N/A (fb0) |
| **Panel HTML** | `backend/app/static/index.html` | Interfaz web 480×320 para navegador | `:8000` |
| **Backend FastAPI** | `backend/app/main.py` | API REST completa (PC, desarrollo) | `:8000` |
| **HMI Router** | `backend/app/api/hmi.py` | Endpoints LED + botón + WebSocket | `:8000` |

---

## API REST

Todos los endpoints disponibles en `http://192.168.88.211:8000`:

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
| `POST` | `/api/button/release` | Registrar liberación |

### Sistema

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/status` | Estado completo (LED + botón + WS clients) |
| `GET` | `/health` | Health check |
| `GET` | `/` | Panel HTML interactivo |

### WebSocket

| Protocolo | Dirección | Descripción |
|-----------|-----------|-------------|
| `WS` | `ws://192.168.88.211:8001/ws` | Canal bidireccional JSON |

Mensajes **Cliente → Servidor:**
```json
{"type": "toggle_led"}
{"type": "button_press"}
{"type": "button_release"}
{"type": "get_status"}
```

Mensajes **Servidor → Cliente:**
```json
{"type": "led_state", "state": true}
{"type": "button_press", "press_count": 5}
{"type": "status", "led": false, "button_pressed": false, "button_press_count": 5}
```

---

## Conexión rápida

### En la Raspberry Pi
```bash
# El servidor arranca automáticamente. Para reiniciar:
ssh pi@192.168.88.211
cd /home/pi/rpi_hmi

# Reiniciar servidor HTTP+WS
pkill -f pi_hmi_server
nohup python3 pi_hmi_server.py > server.log 2>&1 &

# Reiniciar UI framebuffer
sudo pkill -f fb_ui.py
sudo nohup python3 fb_ui.py > /dev/null 2>&1 &
```

### Desde tu PC
```bash
# API
curl http://192.168.88.211:8000/api/status
curl -X POST http://192.168.88.211:8000/api/led/toggle
curl -X POST http://192.168.88.211:8000/api/button/press

# Panel HTML — abre en tu navegador:
# http://192.168.88.211:8000
```

---

## Desarrollo

### Requisitos
- Python 3.11+ (stdlib para la Pi)
- Python 3.13+ con FastAPI + httpx (para PC, opcional)

### Instalar dependencias (PC)
```bash
pip install fastapi uvicorn pydantic pydantic-settings websockets httpx pytest
```

### Ejecutar tests
```bash
# Tests del backend FastAPI (HMI router)
pytest backend/tests/test_hmi.py -v         # 20 tests

# Tests de la UI framebuffer (PixelWriter, fuente, layout)
pytest tests/test_fb_ui.py -v               # 44 tests

# Todos los tests
pytest backend/tests/ tests/ -v             # 64 tests

# Con cobertura
pytest backend/tests/ tests/ -v --cov=backend.app.api.hmi --cov=fb_ui
```

### Resultados (última ejecución)
```
64 passed, 1 warning in 20.97s

backend/tests/test_hmi.py ........ 20/20 ✓
tests/test_fb_ui.py   ............ 44/44 ✓
```

---

## Estructura del proyecto

```
Rpi_Pantalla_V1/
├── pi_hmi_server.py           # Servidor standalone (Pi) — HTTP + WebSocket
├── fb_ui.py                   # UI framebuffer (Pi) — /dev/fb0 + touch
├── fb_test.py                 # Test rápido de framebuffer
├── Rpi_Pantalla_V1.py         # Entrypoint FastAPI (PC)
├── .env / .env.example        # Credenciales SSH y configuración
├── README.md                  # Este documento
│
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app (routers + static)
│   │   ├── config.py          # pydantic-settings
│   │   ├── api/
│   │   │   ├── hmi.py         # Router HMI (LED, botón, WS)
│   │   │   ├── ssh.py         # Router SSH (conexión a Pi)
│   │   │   └── deploy.py      # Router deploy (setup remoto)
│   │   ├── services/
│   │   │   ├── ssh_manager.py # Abstracción SSH (paramiko + mock)
│   │   │   └── deploy_service.py
│   │   ├── hardware/
│   │   │   └── hal.py         # HAL: Device, GPIODriver, Mock
│   │   └── static/
│   │       └── index.html     # Panel HMI HTML5 (480×320)
│   ├── config/
│   │   └── devices.yaml       # Registro declarativo de dispositivos
│   ├── tests/
│   │   ├── test_hmi.py        # Tests del router HMI (20 tests)
│   │   ├── test_ssh_manager.py
│   │   └── test_deploy_service.py
│   └── requirements.txt
│
├── tests/
│   ├── __init__.py
│   └── test_fb_ui.py          # Tests de fb_ui.py (44 tests)
│
├── diagnostics/
│   ├── run_diagnostics.py
│   └── gpio/blink_test.py
│
├── scripts/
│   ├── pi_direct.py           # CLI SSH directa (diagnóstico + setup)
│   ├── pi_display_setup.py    # Asistente configuración pantalla
│   ├── setup_display.sh       # Script bash overlay ads7846
│   └── *.ps1                  # Scripts PowerShell despliegue
│
└── infra/
    └── INSTALL_RASPBIAN_B_PLUS.md  # Guía instalación completa
```

---

## Troubleshooting

### La pantalla está iluminada pero no se ve la UI

**Causa más común:** Falta el overlay `ili9486` (driver de pantalla) en `/boot/config.txt`.
La pantalla ILI9486 necesita **dos** overlays: `ili9486` para el display y `ads7846` para el táctil.

1. **Solución rápida (desde PC):**
   ```bash
   python scripts/fix_display.py --apply
   ```
   Esto añade los overlays correctos y reinicia la Pi.

2. **Solución manual (SSH a la Pi):**
   ```bash
   ssh pi@192.168.88.211
   sudo nano /boot/config.txt
   ```
   Añade estas líneas si faltan:
   ```
   dtparam=spi=on
   dtoverlay=ili9486,rotate=90,speed=32000000
   dtoverlay=ads7846,cs=1,penirq=25,speed=1000000,rotate=270,swapxy=0
   ```
   Guarda y reinicia: `sudo reboot`

3. Verificar que el framebuffer UI está corriendo:
   ```bash
   ssh pi@192.168.88.211 "ps aux | grep fb_ui"
   ```

4. Si no aparece, reiniciarlo:
   ```bash
   ssh pi@192.168.88.211 "cd /home/pi/rpi_hmi && sudo nohup python3 fb_ui.py > /dev/null 2>&1 &"
   ```

5. Verificar resolución del framebuffer:
   ```bash
   ssh pi@192.168.88.211 "cat /sys/class/graphics/fb0/virtual_size"
   # Debe devolver: 720,480
   ```

6. Probar con patrón de test:
   ```bash
   ssh pi@192.168.88.211 "sudo python3 /home/pi/rpi_hmi/fb_test.py"
   ```

### La API no responde
```bash
# Verificar que el servidor corre
ssh pi@192.168.88.211 "ps aux | grep pi_hmi_server"

# Reiniciar si es necesario
ssh pi@192.168.88.211 "pkill -f pi_hmi_server; cd /home/pi/rpi_hmi && nohup python3 pi_hmi_server.py > server.log 2>&1 &"
```

### El WebSocket no conecta
- Asegurar que el puerto 8001 no está bloqueado
- El frontend HTML se conecta a `ws://192.168.88.211:8001/ws`
- Verificar con: `curl http://192.168.88.211:8001/` (debe devolver error, no timeout)

---

## Licencia

MIT

## Autores

- Desarrollado con GitHub Copilot y DeepSeek-V4-Pro
