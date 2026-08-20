# Punto de arranque — Despliegue y cierre de la FASE FINAL

> **LÉEME PRIMERO.** Este archivo es el punto de entrada para un **NUEVO chat de agente**
> que debe **coordinar subagentes** para (1) desplegar lo ya refactorizado y (2) cerrar los
> pendientes que dejó el refactor **más la segunda auditoría externa** (revisión del commit
> `d16f991`, 20/08/2026).
>
> Es **autocontenido**: no hace falta haber participado en el chat anterior. Solo tienes que
> leer este documento y los archivos que aquí se referencian.

---

## 1. Qué es este proyecto

**RPi HMI** — panel de control (Human-Machine Interface) industrial/embebido para Raspberry Pi.

- **Backend:** FastAPI (REST + WebSocket) en `backend/`.
- **Display:** Pygame + DRM/KMS + touch evdev en `display/`.
- **Frontend:** SolidJS + TypeScript en `frontend/`.
- **Hardware:** GPIO (LED **virtual**), SPI TFT ILI9486/piscreen, touch ADS7846/XPT2046.
- **Persistencia:** SQLite (aiosqlite, WAL).
- **Infra:** systemd, despliegue por SSH (Paramiko), CI en GitHub Actions.

Repositorio remoto: `https://github.com/jvelasca/rpi-hmi-pantalla.git` (rama `main`).

---

## 2. Estado actual (snapshot inalterable)

Verificado el **2026-08-20** por el hilo principal (baseline ejecutado localmente):

| Dato | Valor |
|---|---|
| Rama local | `main`, **sincronizada con `origin/main`** (push hecho en el refactor) |
| HEAD | `1987ed9` — `docs: punto de arranque para el proximo chat` (docs-only) |
| Commit auditado (2ª auditoría externa) | `d16f991` — `refactor(Fase 5): ruff 0 errores + pin de version (G)` |
| Relación HEAD ↔ auditado | `1987ed9` = `d16f991` + **solo** `docs/deploy/INICIO.md`. **El código es idéntico al auditado.** |
| Historial del refactor | `64b4812` → `f2b7210` → `5c413f5` → `c1611f4` → `ee6ad9b` → `d16f991` |
| `pytest backend/tests/ display/tests/` | **278 passed / 4 skipped / 0 failed** |
| `mypy app/ --config-file pyproject.toml` (desde `backend/`) | **0 errores** (25 archivos, `strict=true`) |
| `ruff check backend/ display/ scripts/ --config backend/pyproject.toml` | **0 errores** (pineado a `==0.16.3`) |
| `vitest` (frontend) | **16/16 passed** |
| `npm run build` (frontend) | **verde** |

**CI equivalente 100 % verde.** El refactor orquestado está **COMPLETO y commiteado**.

> ⚠️ No reintroducir regresiones. Cualquier subagente que toque código Python debe mantener
> `ruff` + `mypy` + `pytest` en verde; el que toque frontend, `vitest` + `build`.
> **Herramientas locales disponibles:** Python 3.13.7, pytest 8.4.2, ruff 0.16.3, mypy 1.19.1,
> pygame 2.6.1, Node 22 / npm 10. `evdev` NO está instalado (normal en Windows; el touch no lo
> importa a nivel de módulo, usa `os.read` directamente).

---

## 3. Qué ya se hizo (contexto, para no rehacer)

El chat anterior ejecutó un refactor orquestado en 6 fases con 8 subagentes (A1…G).
Cada uno dejó un **handoff** en `docs/audits/refactor/handoffs/<id>.md`.

| Workstream | Fase | Qué aportó |
|---|---|---|
| A1 | 1 | Display: 16 tests corregidos (15 drift + 1 bug feedback botón) + feedback no-bloqueante del botón |
| A2 | 1 | mypy `strict` a 0 errores (57→0); patrón `X = Field(default=...)` (sin `pydantic.mypy`, incompatible) |
| B | 2 | `SECURITY_MODE=local\|protected` + dependencia `require_admin_api_key`; `POST /api/network/*` protegidos; README LED virtual; sudoers mínimo `pi → nmcli` |
| C | 2 | `Screen.allow_mock_fallback`; detección de conector DRM vía sysfs (`_drm_connector_state`) |
| D | 2 | Validación WS con Zod; máquina de estados resync; `VITE_API_URL` sin IP fija |
| E | 3 | Migraciones SQLite versionadas; red no bloqueante (`asyncio.to_thread`); límites systemd; split `StateManager → WebSocketHub` |
| F | 4 | `docs/SECURITY.md` (modelo de amenazas + safe-state); README unificado (278 tests); `frontend/.env.example`; versiones `0.3.0` |
| G | 5 | `ruff` 206→0 + pin `==0.16.3`; 2 bugs reales corregidos (`ERROR` en `widgets.py`, `VENV_PIP` en `deploy_atomic.py`) |

**Documentos de estado clave (léelos según necesites):**

- `docs/audits/refactor/ESTADO.md` — estado global del refactor (cerrado en Fase 5).
- `docs/audits/refactor/PLAN_REFACTOR.md` — plan maestro y mapa de propiedad original.
- `docs/audits/refactor/PROMPTS_SUBAGENTES.md` — ejemplo de prompts autocontenidos.
- `docs/audits/refactor/handoffs/_PLANTILLA.md` — plantilla obligatoria de handoff.
- `docs/SECURITY.md` — política de seguridad y safe-state (referencia de lo acordado).

---

## 4. Segunda auditoría externa — veredicto y comparación

La segunda auditoría (contra `d16f991`) **confirmó que prácticamente todos los problemas
importantes de la primera ya están corregidos** (valoración global 8.7/10, seguridad 5.5→7.8,
arquitectura 8.5→9.2). De sus 28 puntos, esto es lo que realmente queda:

### ✅ Ya corregido (NO rehacer)

Network API protegida + `asyncio.to_thread` · `devices.yaml` LED virtual · WS con Zod + sequence +
resync + snapshot REST · `WebSocketHub` separado de `StateManager` · migraciones versionadas ·
detección DRM por conector · CORS restringido (sin `*` + credentials) · systemd endurecido ·
`asyncio.to_thread` en `NetworkService` · CI ampliado (py3.11/3.12, pytest, ruff, mypy, vitest,
build, smoke, VERSION, archivos prohibidos) · contrato Pydantic↔Zod con `safeParse`.

> **Nota de auditoría propia:** el punto "README sigue diciendo LED GPIO17" de la auditoría
> externa es **stale**. El README actual (líneas 24–31) ya dice que el LED es **virtual** y que
> GPIO17 es la IRQ del touch. Se verificó con `grep` y **ya está corregido** por B/F.

### 🔴 P1 — Bloqueantes de seguridad (código puro, sin hardware)

| # | Hallazgo (2ª auditoría) | Verificado en código | Workstream |
|---|---|---|---|
| P1-1 | `WS /ws` **no autentica** en `protected` (permite `toggle_led`, `press_button`, `release_button`, `display_command` sin API key) | `backend/app/api/ws.py` no usa `require_admin_api_key` | **H1** |
| P1-2 | `/api/led/*`, `/api/button/*`, `/api/display/command` **no siguen** el modelo `protected` | `backend/app/api/hmi.py` sin `Depends(require_admin_api_key)` en los POST | **H1** |
| P1-3 | `X-API-Key` **falta** en CORS `allow_headers` | `backend/app/main.py:188` solo `["Content-Type","Accept"]` | **H1** |
| P1-4 | `allow_mock_fallback=True` por defecto en `Screen` (oculta fallo físico de DRM) | `display/ui/screen.py:107`; el call-site `display/app.py:140` ya cablea `allow_mock_fallback=mock`, pero el **default** de la clase sigue siendo un footgun | **H2** |

### 🟠 P2 — Correcciones de coherencia/robustez (código puro)

| # | Hallazgo (2ª auditoría) | Verificado en código | Workstream |
|---|---|---|---|
| P2-1 | Mensaje engañoso en `config.py`: dice "`/admin/*` expuestos sin protección" pero ssh/deploy devuelven **503** si no hay key | `backend/app/config.py:103-107` | **H1** |
| P2-2 | `_verify_api_key` duplicado en `ssh.py` y `deploy.py` (no usa `deps.py`) | `ssh.py:44-58`, `deploy.py:45-53` | **H1** |
| P2-3 | Validación de red incompleta: no comprueba IP∈subnet, gateway∈subnet, IP≠red, IP≠broadcast | `network_service.py::apply_static` (191-227) | **H3** |
| P2-4 | `/dev/mem` en `ReadWritePaths` del backend (superficie de privilegio) | `config/systemd/rpi-hmi-backend.service:46` | **H6** (decidir en Pi) |
| P2-5 | Falta auditoría de dependencias: `pip-audit`, `bandit`, `npm audit` | `.github/workflows/ci.yml` no los incluye | **H4** |
| P2-6 | README/QUICKSTART con `192.168.88.211` hardcodeada y versiones/strings inconsistentes (`HeaderWidget version="v1.2"` en `display/app.py:184`) | verificado | **H5** (+ fix `v1.2` en **H2**) |

### 🟡 P3 — Mejoras (código o decisión de producto)

| # | Pendiente | Workstream |
|---|---|---|
| P3-1 | Leer `ABS_X`/`ABS_Y` reales del touch vía `EVIOCGABS` (no asumir 4096) | **H2** |
| P3-2 | Implementar `invert_x`/`invert_y` en `raw_to_screen` (hoy código muerto) | **H2** |
| P3-3 | Unificar fuente de versión (`VERSION` → build → Python → FastAPI → frontend) | **H5** |
| P3-4 | Política explícita `startup_policy: off/restore/safe` para futuros actuadores | **H8** (decisión) |
| P3-5 | Watchdog `sd_notify` (`READY=1` + `WATCHDOG=1`) + `Type=notify` + `WatchdogSec=30` | **H3** (opcional, código) |
| P3-6 | Tests HIL (`@pytest.mark.hardware`) + runbook para la Pi | **H6** |

### ⚪ P0 — Requieren HARDWARE (Raspberry Pi física) y decisión

1. Instalar regla sudoers `config/sudoers.d/rpi-hmi` (`sudo install -m 0440 ... && visudo -c`).
2. Crear `.env` de producción: `SECURITY_MODE=protected` + `ADMIN_API_KEY` (32+ chars). **No commitear `.env`.**
3. Verificar `VENV_PIP` en `scripts/deploy_atomic.py` (`f"{PI_BASE}/venv/bin/pip3"` vs `{VENV_PY} -m pip`).
4. Validar límites systemd en la Pi: `systemd-analyze verify` + `systemctl daemon-reload`.
5. Decidir si `/dev/mem` es necesario en `ReadWritePaths` (P2-4) según el driver GPIO real.

---

## 5. Workstreams de esta fase (H1–H8) y mapa de propiedad de archivos

La división respeta **cero colisiones** (cada archivo, un único workstream). Los que no
comparten archivos pueden ir **en paralelo**. Los subagentes **no commitean**: el hilo
principal verifica el gate y hace **commit por workstream**.

| WS | Nombre | Archivos en exclusiva | Requiere HW | Paralelizable | Prioridad |
|---|---|---|---|---|---|
| H1 | Unificar auth REST+WS | `backend/app/api/{ws,hmi,deps,ssh,deploy}.py`, `backend/app/config.py`, `backend/app/main.py` (CORS), `docs/SECURITY.md`, `backend/tests/{test_ws_endpoint,test_hmi,test_config}.py` | No | **No** (primero, es el path crítico) | P1 |
| H2 | Display + touch | `display/ui/{screen,touch}.py`, `display/app.py`, `display/tests/{test_ui,test_display_app}.py` | No | Sí (con H3/H4/H5) | P1/P2/P3 |
| H3 | Red + watchdog | `backend/app/services/network_service.py`, `backend/app/models/network.py`, `backend/tests/test_network.py` (nuevo) | No | Sí | P2/P3 |
| H4 | CI/CD + deps | `.github/workflows/ci.yml`, `backend/pyproject.toml`, `backend/requirements.txt`, `display/requirements.txt` | No | Sí | P2 |
| H5 | Docs/versión | `README.md`, `QUICKSTART.md`, `docs/CONTEXT.md`, `docs/ARCHITECTURE.md`, `.env.example`, `frontend/.env.example` | No | Sí | P2/P3 |
| H6 | Despliegue a la Pi | `config/sudoers.d/rpi-hmi`, `config/systemd/*`, `scripts/deploy*.py`, `.env` (NO commitear), `docs/deploy/runbook.md` (nuevo) | **Sí** | Secuencial (último) | P0 |
| H7 | Arquitectura mayor (HMI vs Admin) | `backend/app/main.py`, `backend/app/api/*`, systemd | No | Solo tras decidir diseño | P3 |
| H8 | Decisiones de producto | — (solo documentar/decidir) | No | Al inicio, con el usuario | P3 |

### Reglas anti-colisión

- `backend/app/main.py` lo posee **H1** (CORS) — H7 solo si se lanza (nunca en paralelo con H1).
- `docs/SECURITY.md` lo posee **H1**; H5 **NO** lo toca (H5 solo README/QUICKSTART/CONTEXT/ARCHITECTURE/.env.example).
- `display/app.py` lo posee **H2** (incluye el fix de `version="v1.2"` del HeaderWidget).
- Los tests son disjuntos por workstream (H1: backend api/config; H3: `test_network.py` nuevo; H2: display).

### Detalle mínimo por workstream

**H1 — Unificar autenticación REST + WS.**
1. Añadir auth al handshake WS: en `protected`, validar `X-API-Key` (header o `Sec-WebSocket-Protocol`) **antes** de `accept()`; en `local`, aceptar sin key. Usar `require_admin_api_key` o un helper nuevo en `deps.py` que permita lectura síncrona del header (el WS no pasa por `Depends`).
2. Añadir `dependencies=[Depends(require_admin_api_key)]` a `POST /api/led/toggle|on|off`, `POST /api/button/press|release`, `POST /api/display/command` en `hmi.py`.
3. Añadir `X-API-Key` a `allow_headers` en `main.py`.
4. Consolidar `_verify_api_key` de `ssh.py`/`deploy.py` en `deps.py` con **dos** dependencias: `require_admin_api_key` (respeta `SECURITY_MODE`) para HMI, y `require_admin_api_key_always` (exige key **siempre**) para `/admin/*`. Documentar la diferencia.
5. Corregir el mensaje de `config.py` (`enable_admin_api` sin key → "inaccesibles (503)", no "expuestos sin protección").
6. Actualizar `docs/SECURITY.md` §2/§3 al modelo unificado (WS y mutadores HMI pasan a PROTECTED).
- **Done:** `pytest backend/tests/` + `mypy` + `ruff` verdes.

**H2 — Display + touch.**
1. Cambiar el default de `Screen.allow_mock_fallback` a `False`; `DisplayApp` debe pasar `allow_mock_fallback=mock` (ya lo hace). Verificar que en producción DRM falla → `exit 1`.
2. Implementar `invert_x`/`invert_y` en `raw_to_screen`; revertir `test_mapping_with_invert` a coordenadas invertidas.
3. Leer `ABS_X`/`ABS_Y` reales vía `EVIOCGABS` (con fallback a `RAW_MAX=4096`).
4. Fix `HeaderWidget(..., version="v1.2")` → `"0.3.0"` en `display/app.py`.
- **Done:** `pytest display/tests/` verde + smoke import de `screen.py`.

**H3 — Red + watchdog (opcional).**
1. Validar coherencia en `apply_static`: IP∈subred, gateway∈subred, IP≠dirección de red, IP≠broadcast. Devolver `NetworkResult(success=False, ...)`.
2. Añadir `backend/tests/test_network.py` (unit, sin nmcli — inyectar/monkeypatch `_run`).
3. (Opcional P3-5) módulo `systemd_notify.py` + `Type=notify` + `WatchdogSec=30` — **solo si el usuario lo confirma**.
- **Done:** `pytest backend/tests/test_network.py` + `mypy` + `ruff` verdes.

**H4 — CI/CD + dependencias.**
1. Añadir `pip-audit` (Python) y `bandit` al workflow; `npm audit` al job de frontend.
2. (Opcional) pin/lock de dependencias exactas.
- **Done:** `ci.yml` válido (YAML) y los checks nuevos reproducibles localmente.

**H5 — Docs/versión.**
1. Eliminar `192.168.88.211` hardcodeada de README/QUICKSTART (dejar `http://<IP_DE_LA_PI>:8000` o `VITE_API_URL`).
2. Unificar conteos de tests y referencias de versión a `0.3.0`.
3. Documentar el modelo `protected` unificado (mutadores HMI + WS) en README/QUICKSTART.
4. Asegurar `frontend/.env.example` documenta `VITE_API_URL`.
- **Done:** sin impacto en tests; revisar que no rompe `npm run build`.

**H6 — Despliegue a la Pi (runbook).** Ejecutar los P0 de §4 y producir `docs/deploy/runbook.md` con pasos exactos + resultado del smoke (`/health`, `/api/status`, curl 401 sin key / 200 con key).

> **H7/H8** requieren decisión del usuario: plantearlas al inicio y **no lanzarlas** sin confirmación.

---

## 6. Protocolo de orquestación (reutilizar el ya probado)

1. **Visión global única** → este chat crea y mantiene `docs/deploy/ESTADO_DESPLEGUE.md`
   (solo lo edita el hilo principal; los subagentes **NO** lo tocan).
2. **Handoff obligatorio** → cada subagente escribe `docs/deploy/handoffs/<ws-id>.md` **antes de
   terminar**, siguiendo `docs/audits/refactor/handoffs/_PLANTILLA.md`.
3. **Saturación vigilada** → si un subagente se queda sin contexto, escribe un checkpoint **parcial**
   con un `## Texto de paso` exacto; el hilo principal relanza con `resume`, **nunca desde cero**.
4. **Cero colisiones** → respetar la tabla de propiedad de §5. Un archivo = un workstream.
5. **Unidad verificable** → **commit por workstream** verificado. El historial git es la memoria inmutable.
6. **Gates** → el hilo principal ejecuta la verificación y commitea **solo si todo verde**.

### Gates de esta fase

| Gate | Criterio | Cuándo |
|---|---|---|
| D1 | `pytest backend/tests/` + `mypy` + `ruff` verdes | tras H1 |
| D2 | `pytest` (backend+display) + `mypy` + `ruff` + `vitest` + `build` verdes | tras H2+H3+H4+H5 |
| D3 | `ci.yml` con los checks nuevos reproducible localmente | tras H4 |
| D4 | servicios vivos en la Pi + HIL verde + runbook firmado | tras H6 |

---

## 7. Cómo arrancar este chat

Pegar lo siguiente como **primer mensaje** del nuevo chat:

```text
Continúa el proyecto RPi HMI desde el punto de arranque docs/deploy/INICIO.md.

Estado: el refactor orquestado (A1..G) está completo y pusheado (HEAD 1987ed9 = d16f991 + docs,
CI verde). La segunda auditoría externa confirmó que casi todo está corregido y dejó un
inventario P0-P3 que cierra la V1.

Haz, en este orden:
1. Lee docs/deploy/INICIO.md (este doc), docs/audits/refactor/ESTADO.md y docs/SECURITY.md.
2. Crea docs/deploy/ESTADO_DESPLEGUE.md y la carpeta docs/deploy/handoffs/.
3. Plantea al usuario las decisiones P3 (H7/H8 y el P3-5 watchdog) antes de lanzarlas.
4. Lanza H1 (seguridad) primero; al verificar su gate D1, abre H2∥H3∥H4∥H5 en paralelo.
5. Cierra con H6 (despliegue a la Pi) y escribe docs/deploy/runbook.md.

Mantén la visión global en ESTADO_DESPLEGUE.md, exige handoff a cada subagente y
commit por workstream verificado. No pierdas contexto entre subagentes. Vigila que
ningún subagente se sature, alucine o rompa la app: si algo no está verde, no commitees.
```

---

## 8. Referencias rápidas

- Handoffs del refactor: `docs/audits/refactor/handoffs/A1.md` … `G.md`.
- Plantilla de handoff: `docs/audits/refactor/handoffs/_PLANTILLA.md`.
- Plan maestro + mapa de propiedad original: `docs/audits/refactor/PLAN_REFACTOR.md`.
- Ejemplos de prompts autocontenidos: `docs/audits/refactor/PROMPTS_SUBAGENTES.md`.
- Seguridad y safe-state: `docs/SECURITY.md`.
- Config de pines (fuente de verdad): `backend/config/devices.yaml`.
- Servicios: `config/systemd/rpi-hmi-backend.service`, `config/systemd/rpi-hmi-display.service`.
