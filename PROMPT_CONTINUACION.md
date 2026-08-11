PROMPT DE CONTINUACIÓN PARA SIGUIENTE HILO
==========================================

CONTEXTO DEL PROYECTO:
Raspberry Pi HMI — Panel de control táctil para Raspberry Pi Model B+ V1.2 (ARMv6, 512MB RAM)
con pantalla 3.5" ILI9486 480x320 (framebuffer real: 720x480@32bpp BGRA) + táctil XPT2046.

RASPBERRY PI — DATOS DE CONEXIÓN:
- IP: 192.168.88.211
- Usuario: pi
- SSH con clave pública (sin password)
- Framebuffer: /dev/fb0 (720x480, 32bpp, BGRA)
- Touch: /dev/input/event0 (XPT2046, rotate=270 en overlay)
- Config display en /boot/config.txt: overlay ili9486 + ads7846

SERVICIOS CORRIENDO EN LA PI:
1. pi_hmi_server.py (PID ~8192): HTTP REST API en puerto 8000 + WebSocket en puerto 8001
   - Sin dependencias externas (stdlib puro)
   - Sirve backend/app/static/index.html como frontend HTML
   - Endpoints: /api/led, /api/button, /api/status, /health
2. fb_ui.py (PID ~21877): UI directa sobre framebuffer /dev/fb0
   - Auto-detecta resolución y formato de píxel
   - Soporte táctil via /dev/input/event*
   - Se comunica con pi_hmi_server.py via HTTP localhost:8000

BACKEND PC (FastAPI):
- backend/app/api/hmi.py: Router con LED, botón, WebSocket (mismos endpoints que la Pi)
- backend/app/main.py: FastAPI app con static files en /
- backend/app/services/ssh_manager.py: Soporte clave SSH pública añadido
- .env: RPI_KEY_PATH añadido como opción

URLs DE ACCESO:
- Panel HTML: http://192.168.88.211:8000
- API REST: http://192.168.88.211:8000/api/status
- WebSocket: ws://192.168.88.211:8001/ws

TESTS (64/64 pasando):
- backend/tests/test_hmi.py: 20 tests (LED toggle, botón, status, integración)
- tests/test_fb_ui.py: 44 tests (PixelWriter 32bpp/16bpp, draw_text, touch mapping, HMIPanel)

ARCHIVOS CLAVE CREADOS/MODIFICADOS:
- pi_hmi_server.py (NUEVO — servidor standalone para Pi)
- fb_ui.py (NUEVO — UI framebuffer con auto-detección)
- backend/app/api/hmi.py (NUEVO — router FastAPI HMI)
- backend/app/static/index.html (NUEVO — frontend HTML 480x320)
- backend/app/main.py (MODIFICADO — routers + static)
- backend/app/services/ssh_manager.py (MODIFICADO — soporte clave SSH)
- backend/app/api/ssh.py (MODIFICADO — key_path en connect)
- backend/app/config.py (MODIFICADO — rpi_key_path)
- .env (MODIFICADO — RPI_KEY_PATH)
- backend/tests/test_hmi.py (NUEVO)
- tests/test_fb_ui.py (NUEVO)
- README.md (REESCRITO — documentación completa)

PROBLEMA RESUELTO:
La pantalla estaba iluminada pero no mostraba nada porque fb_ui.py asumía
480x320@16bpp (RGB565) pero el framebuffer real era 720x480@32bpp (BGRA).
Se reescribió fb_ui.py con auto-detección de resolución/formato desde sysfs.

PENDIENTE / POSIBLES MEJORAS:
- Implementar RealGPIODriver en hal.py (usar gpiozero/lgpio para LED físico en pin 17)
- Configurar systemd services para arranque automático
- Modo kiosk con navegador (Chromium no funciona en ARMv6 sin NEON)
- Añadir más widgets al panel HMI (gráficos, medidores)
- Sincronización de estado entre framebuffer UI y navegador
- Mejorar el mapeo táctil (calibración XPT2046 específica)
- Añadir soporte multi-touch si el controlador lo permite
