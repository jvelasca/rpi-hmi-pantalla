# FASE 2 — Sincronizar documentación con la realidad — ENTRADA

- Rama/base: `main` @ `881ec1a` (cambios de Fase 1 en working tree, sin commit)
- Versión: 0.3.1
- Alcance: **solo documentación** (Markdown). No tocar código, tests ni scripts.

## Objetivo

Dejar `docs/ARCHITECTURE.md` y `README.md` coherentes con el estado real del
proyecto tras la Fase 1 (auth por session-cookie HttpOnly). `docs/SECURITY.md`
ya fue actualizado en Fase 1: solo verificar consistencia y corregir si algo
quedó desalineado.

## Qué está obsoleto / incorrecto (verificado por el orquestador)

### `docs/ARCHITECTURE.md` (muy obsoleto)
- Cabecera dice "Estado: Plan para implementacion" y "Ultima actualizacion 2026-08-11".
- Lista archivos que **ya no existen**:
  - `backend/app/api/router.py`
  - `backend/app/services/display_service.py`
  - `backend/app/hardware/hal.py`, `backend/app/hardware/devices.py`
  - `frontend/src/store/state.ts`
  - `scripts/deploy.sh`, `scripts/setup_pi.sh`, `scripts/build_frontend.sh`, `Makefile`
  - `docs/API.md`, `docs/HARDWARE.md`, `docs/DEVELOPMENT.md`
- `LedState.gpio_pin: default=17` → el real es `default=0` (`models/hmi.py`).
- Endpoint inexistente `GET /api/device/list`.
- Falta documentar: endpoints AUTH (`/api/auth/*`), `settings/display`,
  `display/command`, `network`, `health/live`, `health/ready`; routers admin
  (`/admin/*`, feature-gated); y el nuevo modelo de autenticación por cookie.

### `README.md` (parcialmente desactualizado)
- Badge y sección Tests dicen "332 pytest + 26 vitest" → real **346 pytest + 26 vitest**.
- No documenta el flujo de login del panel web (cuando `SECURITY_MODE=protected`).
- La sección "Configuración de desarrollo" solo menciona `VITE_API_URL`; añadir
  que la auth se hace por cookie de sesión (sin `VITE_API_KEY`).
- La estructura del proyecto omite archivos nuevos (`api/auth.py`, `api/deps.py`,
  `api/health.py`, `api/network.py`, `models/network.py`, `services/ws_hub.py`,
  `services/persistence.py`, `services/network_service.py`, `services/deploy_service.py`,
  `services/ssh_manager.py`, `services/systemd_notify.py`) y componentes frontend
  nuevos (`LoginScreen`, `ConfigScreen`, `ConfigPanel`, `NetworkConfig`,
  `FontSettings`, `ScreenTest`, `TouchCalibration`, `schemas/ws.ts`,
  `hooks/sequenceTracker.ts`, `hooks/useConnectionMonitor.ts`).

## Fuente de verdad (leer antes de escribir)

- `backend/app/main.py` — routers registrados y orden (auth, hmi, ws, network,
  health; admin_ssh/admin_deploy solo con `ENABLE_ADMIN_API=true`), CORS, static.
- `backend/app/api/*.py` — endpoints reales (hmi, ws, network, health, auth, deps,
  ssh, deploy).
- `backend/app/models/*.py` — modelos reales (`hmi.py`, `events.py`, `device.py`,
  `network.py`).
- `backend/app/config.py` — settings reales (incluye `SESSION_TTL_SECONDS`).
- `frontend/src/**` — estructura real de componentes/hooks.
- `docs/SECURITY.md` — ya actualizado en Fase 1: modelo de auth, clasificación de
  endpoints, exención de loopback, modelo de sesión. Úsalo como base de los
  endpoints (está verificado).
- `docs/deploy/handoffs/FASE1_AUTH_CIERRE.md` — resumen de lo que cambió Fase 1.

## Endpoints reales (resumen verificado)

- PUBLIC: `GET /health`, `/health/live`, `/health/ready`, `GET /api/auth/status`.
- AUTH: `POST /api/auth/login` (valida `ADMIN_API_KEY` en body y emite cookie
  `rpi_hmi_session` HttpOnly/SameSite=Strict), `POST /api/auth/logout`.
- LECTURA (públicos): `GET /api/status`, `/api/led`, `/api/button`,
  `/api/display/info`, `/api/settings/display`, `/api/network`.
- PROTECTED (mutadores, exigen `X-API-Key` **o** cookie de sesión en modo
  `protected`, loopback exento): `POST /api/led/toggle|on|off`,
  `POST /api/button/press|release`, `POST /api/display/command`,
  `POST /api/settings/display`, `POST /api/network/static|dhcp`, `WS /ws`
  (clientes no-loopback).
- ADMIN (feature-gated `ENABLE_ADMIN_API=true`, auth siempre):
  `POST /admin/ssh/connect|disconnect|execute`, `GET /admin/ssh/status`,
  `GET /admin/deploy/scan`, `POST /admin/deploy/setup|app|start|stop`,
  `GET /admin/deploy/diagnostics|health`.

## Criterios de aceptación

1. `ARCHITECTURE.md` reescrito: estructura real del repo, endpoints reales
   (incluido auth), modelos reales (`gpio_pin=0`), protocolo WS real (mensajes
   con `version`, `sequence`, `type`, `action`), flujo de auth nuevo, y sección
   de despliegue/systemd acorde al runbook.
2. `README.md` con conteos reales (346 pytest / 26 vitest) y flujo de login
   documentado brevemente.
3. `SECURITY.md` verificado (ya actualizado); solo corregir si algo quedó
   inconsistente (no reescribir).
4. Ningún cambio fuera de `docs/*.md` y `README.md`.

## Verificación

- Docs solo: no se ejecutan tests. Sí se debe comprobar que no quedan
  referencias a archivos/endpoints inexistentes (grep de `router.py`,
  `display_service.py`, `hal.py`, `devices.py`, `store/state.ts`, `deploy.sh`,
  `Makefile`, `device/list`, `gpio_pin=17`).
- Formato Markdown válido (listas/tablas coherentes).

## TEXTO DE PASO (para el cierre, lo completa el subagente)

Al terminar, escribe `docs/deploy/handoffs/FASE2_DOCS_CIERRE.md` con: qué se
reescribió, lista exacta de archivos tocados, y un bloque "TEXTO DE PASO" listo
para la Fase 3 (limpieza de código obsoleto).
