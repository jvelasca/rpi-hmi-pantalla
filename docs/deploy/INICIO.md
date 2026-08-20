# Punto de arranque — Próximo chat: Despliegue y cierre de pendientes

> **LÉEME PRIMERO.** Este archivo es el punto de entrada para un **NUEVO chat de agente**.
> Su objetivo: coordinar subagentes para **desplegar** lo ya refactorizado y **cerrar los
> pendientes** que el refactor dejó documentados. Es autocontenido: no hace falta haber
> participado en el chat anterior.

---

## 1. Qué es este proyecto

**RPi HMI** — panel de control (Human-Machine Interface) industrial/embebido para Raspberry Pi.

- **Backend:** FastAPI (REST + WebSocket) en `backend/`.
- **Display:** Pygame + DRM/KMS + touch evdev en `display/`.
- **Frontend:** SolidJS + TypeScript en `frontend/`.
- **Hardware:** GPIO (LED virtual), SPI TFT ILI9486/piscreen, touch ADS7846/XPT2046.
- **Persistencia:** SQLite (aiosqlite, WAL).
- **Infra:** systemd, despliegue por SSH (Paramiko), CI en GitHub Actions.

Repositorio remoto: `https://github.com/jvelasca/rpi-hmi-pantalla.git` (rama `main`).

---

## 2. Estado actual (snapshot inalterable)

Verificado el **2026-08-20** por el hilo principal del chat anterior:

| Dato | Valor |
|---|---|
| Rama local | `main`, **sincronizada con `origin/main`** (push hecho) |
| HEAD (commit más reciente) | `d16f991` — `refactor(Fase 5): ruff 0 errores + pin de version (G)` |
| Historial del refactor | 6 commits: `64b4812` → `f2b7210` → `5c413f5` → `c1611f4` → `ee6ad9b` → `d16f991` |
| `pytest backend/tests/ display/tests/` | **278 passed / 4 skipped / 0 failed** |
| `mypy app/ --config-file pyproject.toml` | **0 errores** (25 archivos, `strict=true`) |
| `ruff check backend/ display/ scripts/` | **0 errores** (pineado a `==0.16.3`) |
| `vitest` (frontend) | **16/16 passed** |
| `npm run build` (frontend) | **verde** |

**CI equivalente 100 % verde.** El refactor orquestado está **COMPLETO y commiteado**.

> ⚠️ No reintroducir regresiones: cualquier subagente que toque código Python debe mantener
> `ruff` + `mypy` + `pytest` en verde, y el que toque frontend debe mantener `vitest` + `build`.

---

## 3. Qué ya se hizo (contexto, para no rehacer)

El chat anterior ejecutó un refactor orquestado en 6 fases con 8 subagentes (A1…G).
Cada uno dejó un **handoff** en `docs/audits/refactor/handoffs/<id>.md`.

| Workstream | Fase | Qué aportó |
|---|---|---|
| A1 | 1 | Display: 16 tests corregidos (15 drift + 1 bug feedback botón) + feedback no-bloqueante del botón |
| A2 | 1 | mypy `strict` a 0 errores (57→0); `pydantic.mypy` retirado por incompatibilidad, patrón `X = Field(default=...)` |
| B | 2 | `SECURITY_MODE=local\|protected` + dependencia `require_admin_api_key`; `POST /api/network/*` protegidos; README LED virtual; sudoers mínimo `pi → nmcli` |
| C | 2 | `Screen.allow_mock_fallback` (DRM falla → exit 1 en producción); detección de conector DRM vía sysfs |
| D | 2 | Validación WS con Zod; máquina de estados resync; `VITE_API_URL` sin IP fija |
| E | 3 | Migraciones SQLite versionadas; red no bloqueante (`asyncio.to_thread`); límites systemd; split `StateManager → WebSocketHub` |
| F | 4 | `docs/SECURITY.md` (modelo de amenazas + safe-state); README unificado (278 tests); `frontend/.env.example`; versiones `0.3.0` |
| G | 5 | `ruff` 206→0 + pin `==0.16.3`; 2 bugs reales corregidos (`ERROR` no importado en `widgets.py`, `VENV_PIP` en `deploy_atomic.py`) |

**Documentos de estado clave (léelos según necesites):**

- `docs/audits/refactor/ESTADO.md` — estado global del refactor (ya cerrado en Fase 5).
- `docs/audits/refactor/PLAN_REFACTOR.md` — plan maestro y **mapa de propiedad de archivos** original.
- `docs/audits/refactor/PROMPTS_SUBAGENTES.md` — ejemplo de prompts autocontenidos (reutilizable como plantilla).
- `docs/audits/refactor/handoffs/_PLANTILLA.md` — plantilla obligatoria de handoff.
- `docs/SECURITY.md` — política de seguridad y safe-state (referencia de lo ya acordado).

---

## 4. Qué queda: inventario de pendientes

Fuentes: `ESTADO.md` §Pendientes + hallazgos de la **auditoría externa** no abordados en el
refactor. Clasificados por prioridad y por si requieren **hardware** (Raspberry Pi física) o no.

### 🔴 P0 — Bloqueantes de un despliegue real seguro (requieren hardware y decisión)

1. **Instalar la regla sudoers** `config/sudoers.d/rpi-hmi` en la Pi (`pi → /usr/bin/nmcli`).
   Sin esto, `NetworkService` no puede ejecutar `sudo nmcli`.
   - Acción: `sudo install -m 0440 config/sudoers.d/rpi-hmi /etc/sudoers.d/ && sudo visudo -c`.
2. **Configurar `.env` de producción**: `SECURITY_MODE=protected` + `ADMIN_API_KEY` (32+ chars).
   - Si se deja `local`, `POST /api/network/*` siguen abiertos en la LAN.
3. **Verificar `VENV_PIP`** en `scripts/deploy_atomic.py`: quedó `f"{PI_BASE}/venv/bin/pip3"`;
   confirmar que es la intención o cambiarlo a `{VENV_PY} -m pip`.
4. **Validar límites systemd** en la Pi: `systemd-analyze verify` + `systemctl daemon-reload`.

### 🟠 P1 — Cierre de seguridad y robustez (código, sin hardware)

5. **Consolidar `_verify_api_key`**: `backend/app/api/ssh.py` y `deploy.py` duplican la lógica de
   auth que ya vive en `backend/app/api/deps.py::require_admin_api_key`. Unificar.
6. **Extender `SECURITY_MODE=protected`** a `/api/led/*`, `/api/button/*` y `/ws` (hoy solo cubre
   `POST /api/network/*`). Decidir y documentar en `docs/SECURITY.md`.
7. **`toggle` vs `set`** (hallazgo #5): añadir `PUT /api/led {state: bool}` (SET ON/OFF) además de
   `toggle`, para eliminar la ambigüedad semántica distribuida.
8. **Watchdog backend** (hallazgo #20): implementar `sdnotify` (`READY=1` + `WATCHDOG=1`), cambiar
   systemd a `Type=notify` y recién entonces añadir `WatchdogSec=30`.
9. **Tests de migraciones SQLite**: hoy validadas por smoke manual (E); añadir test unitario dedicado.
10. **Touch**: implementar `invert_x`/`invert_y` en `raw_to_screen` (hoy son código muerto) y
    revertir `test_mapping_with_invert` a las coordenadas invertidas.
11. **`RAW_MAX` desde `EVIOCGABS`** (hallazgo #13): no asumir `0..4096`; leer capacidades reales del
    dispositivo táctil.

### 🟡 P2 — Calidad, observabilidad y endurecimiento (sin hardware)

12. **Health check coherente** (hallazgo #18): definir explícitamente qué significa `/health/ready`
    (API+DB vs API+DB+GPIO+Display) y documentarlo.
13. **Tests HIL** (hallazgo #23): categorizar `UNIT/INTEGRATION` vs `HARDWARE` con un marcador
    `@pytest.mark.hardware` y un runbook para ejecutar en la Pi (DRM, GPIO, touch, ILI9486).
14. **CI endurecido** (hallazgo #24): `pip-audit`, `npm audit`, `bandit`, `gitleaks`.
15. **Lock de dependencias** (hallazgo #25): `requirements.txt` con versiones exactas (o pip-tools),
    más allá del pin de `ruff` ya hecho.
16. **Frontend**: encapsular `setInterval` de `App.tsx` en un hook `useConnectionMonitor` (hallazgo #10).
17. **Tipos TS desde OpenAPI** (hallazgo #22): generar `types/api.ts` desde el schema OpenAPI para
    eliminar la duplicación manual Pydantic↔TS.
18. **`driver=="fb"` no distinguido** en `Screen.init()` (solo distingue mock vs no-mock); preexistente.

### ⚪ P3 — Arquitectónico / decisión de producto (requieren decisión previa)

19. **Separar HMI runtime de Admin service** (hallazgos #27/#32): mover SSH/deploy/network a un
    servicio/puerto separado (`:8001`) y firewall. Es la evolución mayor pendiente.
20. **Semántica del botón** (no bloqueante): el auto-release usa `_button_press_duration=2` (~100 ms)
    y dispara `POST /api/button/release`. Confirmar si se quiere "flash visual" o "mantener pulsado".
21. **Realinear pydantic↔mypy** (opcional): recuperar el plugin `pydantic.mypy` alineando versiones,
    o mantener el patrón actual `X = Field(default=...)`.

---

## 5. Workstreams propuestos para este chat

La división respeta el principio de **cero colisiones** (cada archivo, un único workstream).
Se sugiere este orden; los que no comparten archivos pueden ir en paralelo.

| WS | Nombre | Archivos en exclusiva | Requiere HW | Paralelizable |
|---|---|---|---|---|
| H1 | Cierre de seguridad | `backend/app/api/{ssh,deploy,deps,hmi,ws}.py`, `backend/app/config.py`, `docs/SECURITY.md` | No | Tras H1 empieza todo lo demás |
| H2 | Touch + display | `display/ui/{touch,screen}.py`, `display/tests/test_ui.py` | No | Sí (con H3) |
| H3 | Observabilidad backend | `backend/app/services/{persistence,state_manager}.py`, `backend/app/services/systemd_notify.py` (nuevo), `backend/app/api/health.py`, `backend/tests/**`, `config/systemd/rpi-hmi-backend.service` | No | Sí (con H2) |
| H4 | Frontend | `frontend/src/**`, `frontend/package.json` | No | Sí |
| H5 | CI/CD + deps | `.github/workflows/ci.yml`, `backend/pyproject.toml`, `backend/requirements.txt`, `display/requirements.txt` | No | Sí |
| H6 | Despliegue a la Pi | `config/sudoers.d/rpi-hmi`, `config/systemd/*`, `scripts/deploy*.py`, `.env` (NO commitear), `docs/deploy/runbook.md` (nuevo) | **Sí** | Secuencial (último) |
| H7 | Arquitectura mayor (HMI vs Admin) | `backend/app/main.py`, `backend/app/api/*`, systemd | No | Solo tras decidir diseño |
| H8 | Decisiones de producto | — (solo documentar/decidir) | No | Al inicio, con el usuario |

### Detalle mínimo por workstream

**H1 — Cierre de seguridad.**
1. Mover `_verify_api_key` de `ssh.py`/`deploy.py` a usar `require_admin_api_key` (import de `deps.py`).
2. Decidir y aplicar si `SECURITY_MODE=protected` debe cubrir `/api/led`, `/api/button`, `/ws`.
3. Añadir `PUT /api/led {state}` (SET) conservando `toggle`.
4. Actualizar `docs/SECURITY.md` §2/§3 en consecuencia.
- Done: `pytest backend/tests/` + `mypy` + `ruff` verdes.

**H2 — Touch + display.**
1. Implementar `invert_x`/`invert_y` en `raw_to_screen`; revertir `test_mapping_with_invert`.
2. Obtener `RAW_MAX` de `EVIOCGABS` en vez de asumir 4096 (con fallback).
3. Distinguir `driver=="fb"` en `Screen.init()`.
- Done: `pytest display/tests/` verde.

**H3 — Observabilidad backend.**
1. Test unitario de migraciones SQLite (BD nueva y BD legacy → `schema_version` correcto, datos preservados).
2. Watchdog: módulo `systemd_notify.py` (`READY=1`, `WATCHDOG=1`), `Type=notify` + `WatchdogSec=30`.
3. Definir `/health/ready` (API+DB+GPIO+Display) y documentarlo.
- Done: `pytest backend/tests/` + `mypy` + `ruff` verdes.

**H4 — Frontend.**
1. Extraer el `setInterval` de `App.tsx` a `useConnectionMonitor()`.
2. (Opcional/amplio) Generación de tipos TS desde OpenAPI.
- Done: `vitest` + `npm run build` verdes.

**H5 — CI/CD + dependencias.**
1. Pin/lock de dependencias Python (versiones exactas).
2. Añadir `pip-audit`, `npm audit`, `bandit`, `gitleaks` al workflow.
- Done: `ci.yml` verde (local: reproducir los checks nuevos).

**H6 — Despliegue a la Pi (runbook).**
1. Instalar sudoers + `visudo -c`.
2. Crear `.env` de producción (`SECURITY_MODE`, `ADMIN_API_KEY`). **No commitear `.env`.**
3. `systemd-analyze verify` + `systemctl daemon-reload` + arrancar servicios.
4. Verificar `VENV_PIP` en `deploy_atomic.py`.
5. Smoke: `/health`, `/api/status`, y validación de endpoints protegidos (curl 401 sin key / 200 con key).
6. Ejecutar tests HIL en la Pi.
- Entregable: `docs/deploy/runbook.md` con pasos exactos y resultado.

> **H7/H8** requieren decisión del usuario: plantearlas al inicio y no lanzarlas sin confirmación.

---

## 6. Protocolo de orquestación (reutilizar el ya probado)

El chat anterior demostró un protocolo que funcionó. **Mantenerlo**:

1. **Visión global única** → este chat crea y mantiene `docs/deploy/ESTADO_DESPLEGUE.md`
   (solo lo edita el hilo principal; los subagentes NO lo tocan).
2. **Handoff obligatorio** → cada subagente escribe `docs/deploy/handoffs/<ws-id>.md` **antes de
   terminar**, siguiendo `docs/audits/refactor/handoffs/_PLANTILLA.md`.
3. **Saturación vigilada** → si un subagente se queda sin contexto, escribe un checkpoint **parcial**
   con un `## Texto de paso` exacto; el hilo principal relanza con `resume`, nunca desde cero.
4. **Cero colisiones** → respetar la tabla de propiedad de §5. Un archivo = un workstream.
5. **Unidad verificable** → commit por workstream verificado. El historial git es la memoria inmutable.
6. **Gates** → el hilo principal ejecuta la verificación y commitea solo si todo verde.

### Gates de este chat

| Gate | Criterio |
|---|---|
| D1 (tras H1) | `pytest backend/tests/` + `mypy` + `ruff` verdes |
| D2 (tras H2+H3+H4) | `pytest` (backend+display) + `mypy` + `ruff` + `vitest` + `build` verdes |
| D3 (tras H5) | `ci.yml` con los checks nuevos reproducible localmente |
| D4 (tras H6) | servicios vivos en la Pi + HIL verde + runbook firmado |

---

## 7. Cómo arrancar este chat

Pegar lo siguiente como **primer mensaje** del nuevo chat:

```text
Continúa el proyecto RPi HMI desde el punto de arranque docs/deploy/INICIO.md.

Estado: el refactor orquestado (A1..G) está completo y pusheado (HEAD d16f991, CI verde).
Ahora hay que desplegar lo refactorizado y cerrar los pendientes.

Haz, en este orden:
1. Lee docs/deploy/INICIO.md (este doc), docs/audits/refactor/ESTADO.md y docs/SECURITY.md.
2. Crea docs/deploy/ESTADO_DESPLEGUE.md y la carpeta docs/deploy/handoffs/.
3. Plantea al usuario las decisiones P3 (H7/H8) antes de lanzarlas.
4. Lanza H1 (seguridad) primero; al verificar su gate, abre H2∥H3∥H4∥H5 en paralelo.
5. Cierra con H6 (despliegue a la Pi) y escribe docs/deploy/runbook.md.

Mantén la visión global en ESTADO_DESPLEGUE.md, exige handoff a cada subagente y
commit por workstream verificado. No pierdas contexto entre subagentes.
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
