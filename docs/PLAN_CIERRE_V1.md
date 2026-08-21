# PLAN DE CIERRE V1 — Auditoría, correcciones y refactorización

> Veredicto de la auditoría externa contrastado con el código real, más un plan
> de corrección/refactorización ejecutable por subagentes, con handoffs,
> documentación, tests y limpieza.
>
> Fecha: 2026-08-20 · HEAD: `881ec1a` · Versión: 0.3.1 · Estado: V1 no en producción

---

## 1. Veredicto de la auditoría (contrastado con el código)

La auditoría externa es **esencialmente correcta**. Se verificó cada uno de sus 17
puntos contra el código actual y todos los verdes (`🟢`) se confirman. El único
punto importante pendiente (`🔴 17`) se confirma y se amplía.

### Confirmación de los 16 puntos verdes

| # | Punto | Estado real |
|---|---|---|
| 1 | `startup_policy` (`off/restore/safe`, default `restore`) | ✅ `config.py:85` |
| 2 | `require_admin_api_key` + `require_admin_api_key_always` | ✅ `deps.py`; usados en `deploy.py`/`ssh.py` |
| 3 | Modelo de seguridad REST coherente (loopback exento en `protected`) | ✅ `deps.py` `_is_loopback_client` |
| 4 | Mutadores HMI REST protegidos | ✅ `hmi.py` (LED/button/settings/display command) |
| 5 | Network API (GET público, POST protegido, `to_thread`) | ✅ `network.py` |
| 6 | WS auth (header / subprotocolo / `?token=`) | ✅ `ws.py` `_extract_api_key_candidates` |
| 7 | `DisplayAction` fuente única REST/WS | ✅ `models/hmi.py:103` + `models/events.py:15` |
| 8 | Sequence tracking global con marca de agua | ✅ `sequenceTracker.ts` + `useWebSocket.ts` |
| 9 | `WebSocketHub` con cola limitada (drop-oldest) | ✅ `ws_hub.py` `BROADCAST_QUEUE_MAXSIZE=100` |
| 10 | Display REST no-bloqueante (worker + `_apply_rest_results`) | ✅ `display/app.py` |
| 11 | Touch real (EV_ABS/ABS_X/ABS_Y + EVIOCGABS, sin fallback ciego) | ✅ `display/ui/touch.py` |
| 12 | Migraciones idempotentes legacy (001 → 002) | ✅ `persistence.py` |
| 13 | `gpio_pin` eliminado de SQLite; LED virtual | ✅ `persistence.py` + `devices.yaml` (`pin: null`) |
| 14 | systemd watchdog/hardening (`Type=notify`, `WatchdogSec=30`) | ✅ `*.service` + `systemd_notify.py` |
| 15 | Versionado único (`VERSION` → `_version.py` → FastAPI/display) | ✅ `0.3.1` en `VERSION`, `pyproject.toml`, `package.json` |
| 16 | Documentación mucho mejor (SECURITY.md, README, ESTADO_DESPLEGUE) | ✅ con excepciones (ver §2.2) |

### Confirmación del punto 17 (el único importante)

`VITE_API_KEY` **se inyecta en el bundle del navegador**:

- `frontend/src/hooks/useWebSocket.ts:29` → `const API_KEY = import.meta.env.VITE_API_KEY`
- `frontend/src/hooks/useApi.ts:22` → `const API_KEY = import.meta.env.VITE_API_KEY`

Al hacer `npm run build`, Vite **sustituye literalmente** el valor en el JS
compilado (`frontend/dist/assets/index-*.js`), que FastAPI sirve estáticamente en
`/`. Cualquiera que cargue la página (navegador de la LAN, `curl`, DevTools) puede
leer la clave. Consecuencia: en `SECURITY_MODE=protected`, la clave que protege
REST mutador y WS queda expuesta a cualquier host de la LAN que acceda al panel web,
anulando la protección para ese vector.

Esto es **coherente con el fallo** de la auditoría y es el P0 del plan.

---

## 2. Hallazgos adicionales (no cubiertos por la auditoría externa)

### 2.1 P0 — `VITE_API_KEY` expuesta (detalle y opciones)

Ver §3 (Fase 1). Decisión de diseño que requiere aprobación del usuario.

### 2.2 Documentación desactualizada

- `docs/ARCHITECTURE.md` está obsoleta: dice "Estado: Plan para implementacion" y
  "Ultima actualizacion: 2026-08-11"; lista archivos que ya no existen
  (`api/router.py`, `services/display_service.py`, `hardware/hal.py`,
  `hardware/devices.py`, `frontend/src/store/state.ts`, `scripts/deploy.sh`,
  `Makefile`), usa `gpio_pin: default=17` en el ejemplo de `LedState` (hoy `0`),
  y lista un endpoint inexistente `GET /api/device/list`.
- Faltan por documentar los componentes/hooks nuevos (ConfigScreen, NetworkConfig,
  FontSettings, ScreenTest, TouchCalibration, `schemas/ws.ts`, `sequenceTracker.ts`).

### 2.3 Código obsoleto

- `legacy/` completo (`hal.py`, `pi_hmi_server.py`, `fb_probe.py`, `fb_ui.py`,
  `static/index.html`, `README.md`): implementación pre-refactor, totalmente
  superada por `backend/` + `display/`.
- `Rpi_Pantalla_V1.py` en la raíz: script suelto sin uso.
- `scripts/` con proliferación de scripts de deploy solapados:
  `deploy.py`, `deploy_atomic.py`, `deploy_frontend.py`, `deploy_step.py`,
  `rollback.py`, `display_probe.py`, `post_reboot_check.py`, `ili9486_driver.py`
  (Python) + múltiples `.ps1` y `.sh` + `.dts`. Falta un único camino de deploy.
- `diagnostics/` y `tests/test_fb_ui.py` (raíz): revisar si siguen aportando.

### 2.4 Acumulación de handoffs históricos

- `docs/handoffs/`, `docs/deploy/handoffs/`, `docs/audits/refactor/handoffs/`
  contienen documentos intermedios ya superados. Deben archivarse a
  `docs/archive/` para no confundir al siguiente agente.

---

## 3. Plan por fases (ejecución con subagentes + handoffs)

> Orden secuencial. Cada fase = un subagente (o pocos), un handoff de cierre y un
> texto de paso. Antes de cada fase: baseline verde (tests + git limpio).

### Fase 0 — Baseline y precondiciones (orquestador, sin subagente de código)

- Ejecutar la suite completa y registrar números reales: `pytest backend/tests/
  display/tests/`, `ruff`, `mypy`, `bandit`, `pip-audit`; `npm test`, `npm run
  build`, `npm audit` en `frontend/`.
- Registrar `git status` limpio y HEAD (`881ec1a`).
- **Entregable:** `docs/CONTEXT.md` actualizado con el baseline; arranca el
  handoff de la Fase 1.
- **Decisión previa necesaria:** elegir la opción de auth de la Fase 1 (ver abajo).

### Fase 1 (P0) — Eliminar la exposición de la API key en el navegador

**Decisión de diseño (requiere aprobación del usuario):**

- **Opción A (recomendada) — Session cookie HttpOnly + API key solo para M2M.**
  - Añadir `POST /api/auth/login` (acepta `ADMIN_API_KEY` o clave UI separada) y
    `POST /api/auth/logout`; emitir cookie `HttpOnly; Secure; SameSite=Strict`.
  - Las dependencias `require_admin_api_key` / WS aceptan **o bien** `X-API-Key`
    (scripts/M2M) **o bien** la cookie de sesión (navegador).
  - Eliminar `VITE_API_KEY` del frontend; añadir un login mínimo en el panel web.
  - La clave nunca llega al JS del navegador.
- **Opción B — Tratar el panel web same-origin como cliente de confianza (loopback).**
  - Eliminar `VITE_API_KEY`; el panel web (mismo origen que el backend) se autentica
    vía cookie de sesión **anónima de primer acceso** o se confía por `Origin`/`Referer`
    hacia el propio host. Más simple, algo más laxo.
- **Opción C — Documentar la limitación y renombrar la variable.**
  - Mantener el mecanismo actual pero **renombrar** `VITE_API_KEY` → `VITE_PANEL_TOKEN`
    y documentar explícitamente en `SECURITY.md` que, si se compila en el bundle, la
    clave es pública para la LAN. Solo válida si se acepta el riesgo.

**Alcance técnico (Opción A):**
- `backend/app/api/auth.py` (nuevo): login/logout + gestión de sesión (en memoria o
  cookie firmada con `itsdangerous`/HMAC).
- `backend/app/api/deps.py`: aceptar cookie de sesión en `require_admin_api_key`
  (y una variante para WS).
- `backend/app/api/ws.py`: autenticar WS por cookie de sesión (además de
  header/subprotocolo/token).
- `frontend/`: eliminar `VITE_API_KEY`; añadir pantalla de login; propagar cookie.
- `SECURITY.md`, `.env.example`, `frontend/.env.example`.
- **Tests:** nuevos `test_auth.py` (login, cookie válida/inválida, expiración,
  WS con cookie) + tests frontend del flujo de login.
- **Verificación:** pytest + vitest + build + bandit.

### Fase 2 — Sincronizar documentación con la realidad

- Reescribir `docs/ARCHITECTURE.md` (estructura real, endpoints reales, modelos
  reales con `gpio_pin=0`, WS protocol, flujo de auth nuevo).
- Actualizar `docs/SECURITY.md` con el modelo de auth de la Fase 1.
- Actualizar `README.md` (conteos de tests reales del baseline).
- **Entregable:** docs coherentes con v0.3.x.

### Fase 3 — Limpieza de código obsoleto

- Eliminar `legacy/` tras confirmar (grep) que nada lo importa.
- Eliminar `Rpi_Pantalla_V1.py` y `tests/test_fb_ui.py` (si no aportan).
- Consolidar `scripts/deploy*.py` en un único `scripts/deploy.py` documentado;
  retirar `deploy_atomic.py`, `deploy_frontend.py`, `deploy_step.py`, `rollback.py`
  (o archivar a `docs/archive/`).
- Revisar `scripts/*.ps1` y `scripts/*.dts` (mantener solo lo usado por el runbook).
- Actualizar `scripts/setup_rpi.sh` / runbook si se renombra algo.
- **Verificación:** CI `release-smoke` (chequeo de ficheros prohibidos) + pytest.
- **Entregable:** repo limpio, CI verde.

### Fase 4 — Hardening y mejoras menores

- Verificar `.gitattributes` (LF en config Linux) y `config/sudoers.d/rpi-hmi`.
- Revisar resolución de display hardcodeada (`480x320`) en `main.py` y `display/app.py`
  (opcional: leer del overlay/config).
- Añadir rate-limiting mínimo al endpoint de login (anti brute-force).
- Revisar que `README.md` y `ESTADO_DESPLEGUE.md` reflejen el estado final.
- **Tests:** los necesarios para cada micro-cambio.

### Fase 5 — Verificación final y cierre

- Suite completa: pytest, ruff, mypy, bandit, pip-audit, vitest, build, npm audit.
- Verificar coherencia de versión (`VERSION`, `pyproject.toml`, `package.json`) y
  decidir bump a `0.3.2`.
- Actualizar `docs/ESTADO_DESPLEGUE.md`, `docs/CONTEXT.md`.
- **Entregable:** documento de cierre con todo verde + texto de paso final.

---

## 4. Decisiones aprobadas (2026-08-20)

1. **Opción de auth (Fase 1):** ✅ **A** — session-cookie HttpOnly + login mínimo;
   la API key queda solo para scripts/M2M.
2. **Alcance de la limpieza (Fase 3):** ✅ **Eliminar definitivamente** (legacy/,
   scripts duplicados, Rpi_Pantalla_V1.py).
3. **Versionado final:** ✅ **bump a `0.3.2`** al cerrar.
