# FASE 2 — Sincronizar documentación con la realidad — CIERRE

- Rama/base: `main` @ `881ec1a` (working tree, sin commit)
- Versión: 0.3.1
- Resumen: Se reescribió `docs/ARCHITECTURE.md` (obsoleto) y se actualizó
  `README.md` para reflejar el estado real del proyecto tras la Fase 1 (auth por
  session-cookie HttpOnly). `docs/SECURITY.md` se verificó y no requirió cambios.
  Solo Markdown: no se tocó código, tests, scripts, `legacy/`, `.env` ni versiones.

## Cambios

### Modificados
- `docs/ARCHITECTURE.md` — reescrito por completo:
  - Cabecera "Estado: Implementado (V1, no en producción)" (antes "Plan para
    implementacion").
  - Estructura del proyecto real (backend: `api/auth.py`, `api/deps.py`,
    `api/health.py`, `api/network.py`, `api/ssh.py`, `api/deploy.py`,
    `models/device.py`, `models/network.py`, `services/ws_hub.py`,
    `services/persistence.py`, `services/network_service.py`,
    `services/deploy_service.py`, `services/ssh_manager.py`,
    `services/systemd_notify.py`; frontend: `LoginScreen`, `ConfigScreen`,
    `ConfigPanel`, `NetworkConfig`, `FontSettings`, `ScreenTest`,
    `TouchCalibration`, `schemas/ws.ts`, `hooks/sequenceTracker.ts`,
    `hooks/useConnectionMonitor.ts`).
  - Eliminados los archivos inexistentes (`api/router.py`,
    `services/display_service.py`, `hardware/hal.py`, `hardware/devices.py`,
    `frontend/src/store/state.ts`, `scripts/deploy.sh`, `scripts/setup_pi.sh`,
    `Makefile`, `docs/API.md`, `docs/HARDWARE.md`, `docs/DEVELOPMENT.md`).
  - Endpoints reales: health, auth (`/api/auth/*`), HMI, `settings/display`,
    `display/command`, `network`, admin (`/admin/ssh/*`, `/admin/deploy/*`,
    feature-gated). Eliminado el inexistente `GET /api/device/list`.
  - Protocolo WS real (sobre con `version`/`type`/`sequence`/`timestamp`, acciones
    `display_command`, `display_settings_changed`, `display_changed`, etc.).
  - Modelos reales: `LedState.gpio_pin` con `default=0` (antes `17`); LED virtual.
  - Nueva sección de autenticación (flujo login/cookie) y de persistencia SQLite.
  - Sección de despliegue/systemd acorde a `docs/deploy/runbook.md`.
- `README.md` — actualizado:
  - Badge y sección Tests: `332 pytest` → **`346 pytest`** (+ 26 vitest).
  - Nueva subsección "Autenticación del panel web" con el flujo de login
    (`POST /api/auth/login` → cookie `rpi_hmi_session` HttpOnly) y nota de que ya
    no existe `VITE_API_KEY`.
  - "Configuración de desarrollo": aclarado que la auth es por cookie de sesión.
  - "Estructura del proyecto" reescrita con los archivos nuevos de backend y
    frontend.

### Verificados (sin cambios)
- `docs/SECURITY.md` — verificado contra `backend/app/api/*.py`,
  `backend/app/config.py` y `backend/app/models/*.py`. Los endpoints, la
  clasificación (PUBLIC/AUTH/PROTECTED/ADMIN), el modelo de sesión y las variables
  (`SECURITY_MODE`, `ADMIN_API_KEY`, `ENABLE_ADMIN_API`, `SESSION_TTL_SECONDS`)
  coinciden con el código. No se requirió ninguna corrección.

### Creados
- `docs/deploy/handoffs/FASE2_DOCS_CIERRE.md` — este documento.

## Verificación

- No se ejecutan tests (cambio solo de documentación).
- Grep de referencias obsoletas (`router.py`, `display_service.py`, `hal.py`,
  `devices.py`, `store/state.ts`, `deploy.sh`, `Makefile`, `device/list`,
  `gpio_pin=17`) sobre los tres documentos tocados:
  - `docs/ARCHITECTURE.md` → **0 coincidencias**.
  - `README.md` → **0 coincidencias**.
  - `docs/SECURITY.md` → **0 coincidencias**.
- Las únicas coincidencias del repo están en otros documentos **fuera de alcance**
  (históricos/planificación): `docs/deploy/handoffs/FASE2_DOCS.md`,
  `docs/PLAN_CIERRE_V1.md`, `docs/audits/*`. Corresponden a la limpieza de
  `legacy/` (Fase 3) y no se tocaron.

## Decisiones

- **`SECURITY.md` sin cambios**: ya estaba alineado con el código (actualizado en
  Fase 1). Se priorizó no reescribir y solo verificar, según el alcance.
- **`ARCHITECTURE.md` reescrito en español con tildes** (coherente con
  `README.md`/`SECURITY.md`), no en el estilo ASCII previo.
- **Se eliminó la sección "Plan de implementación"** del antiguo
  `ARCHITECTURE.md`: era una tabla de fases obsoleta (referenciaba `Makefile` y
  `setup_pi.sh` ya inexistentes).
- **GPIO 17 solo se conserva como referencia legítima al touch IRQ** en la sección
  de hardware del `README.md` (XPT2046 `TP_IRQ`/pendown); no como `gpio_pin` del LED.
- **`hardware/` documentado como placeholder**: su `__init__.py` solo existe como
  reserva para futuras interfaces I2C/SPI/PWM (la HAL GPIO vive en `gpio_service.py`).

## Pendientes / fuera de alcance

- **Fase 3 — limpieza de código obsoleto**: eliminación/archivado de `legacy/`
  (`hal.py`, `pi_hmi_server.py`, `fb_probe.py`, `fb_ui.py`, etc.) y de referencias
  obsoletas en `docs/PLAN_CIERRE_V1.md` y `docs/audits/*`. No tocado aquí.
- **Fase 4 — rate-limiting del login** (anti brute-force): pendiente.
- **Fase 5 — versionado 0.3.2**: el bump de versión no corresponde a esta fase.
- `docs/PLAN_MAESTRO.md` no se modificó (fuera de alcance; puede contener aún
  referencias de planificación a revisar en su propia fase).

## TEXTO DE PASO (pegar en el siguiente chat)

"Proyecto en `881ec1a` (working tree, sin commit). Fase 2 completada: documentación
sincronizada con el código real. Se reescribió `docs/ARCHITECTURE.md` (estructura
real, endpoints reales incluido auth y admin, modelo `gpio_pin=0`, protocolo WS con
`version`/`sequence`/`type`/`action`, flujo de login por cookie, persistencia SQLite,
systemd) y se actualizó `README.md` (conteos 346 pytest + 26 vitest, flujo de login
del panel web, estructura de proyecto con archivos nuevos). `docs/SECURITY.md`
verificado sin cambios. Grep de referencias obsoletas en los 3 documentos: 0
coincidencias. Archivos: docs/ARCHITECTURE.md, README.md,
docs/deploy/handoffs/FASE2_DOCS_CIERRE.md. Pendientes detectados: limpieza de
`legacy/` y referencias obsoletas en docs (Fase 3), rate-limiting login (Fase 4),
versionado 0.3.2 (Fase 5). Siguiente fase: Fase 3 — limpieza de código obsoleto
(eliminar/archivar `legacy/` y referencias obsoletas en docs). Lee
docs/deploy/handoffs/FASE2_DOCS_CIERRE.md para el detalle."
