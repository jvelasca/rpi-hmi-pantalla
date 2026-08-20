# Estado Global del Despliegue y Cierre de la FASE FINAL

> **ÚNICO editor de este archivo: el hilo principal.**
> Los subagentes escriben en `docs/deploy/handoffs/<ws-id>.md` y devuelven su resumen; jamás editan aquí.

## Estado general

- **Fase actual:** FASE FINAL — código cerrado (H1–H9). Queda **H6 (hardware)** y validación en Pi de **H9**.
- **Última actualización:** 2026-08-20
- **Commit base (restauración):** `d16f991` (HEAD actual `912e9a7`)
- **Puerta de calidad actual:** pytest = 318 passed / 9 skipped · mypy = 0 · ruff = 0 · vitest = 16/16 · build OK

## Workstreams

| ID | Nombre | Prioridad | Estado | Handoff | Commit |
|---|---|---|---|---|---|
| H1 | Unificar auth REST+WS (seguridad) | P1 | ✅ completado | `handoffs/H1.md` | `1c5bcf1` |
| H2 | Display + touch | P1/P2/P3 | ✅ completado | `handoffs/H2.md` | `e6170de` |
| H3 | Red (validación) | P2 | ✅ completado | `handoffs/H3.md` | `d8ff3dd` |
| H4 | CI/CD + dependencias | P2 | ✅ completado | `handoffs/H4.md` | `0802149` |
| H5 | Docs/versión | P2/P3 | ✅ completado | `handoffs/H5.md` | `c2a3db1` |
| H6 | Despliegue a la Pi (scripts + runbook + HIL) | P0 | ✅ código listo (ejecución en la Pi pendiente) | `handoffs/H6-deploy.md`, `handoffs/H6-hil.md` | `8203970`, `92fa837`, `52f46c4` |
| H7 | Arquitectura mayor (HMI vs Admin) | P3 | ⏭️ diferido (decisión: no separar ahora) | — | — |
| H8 | `startup_policy` (actuadores) | P3 | ✅ completado | `handoffs/H8.md` | `64bbf14` |
| H8-button | Semántica del botón (toggle LED) | P3 | ✅ completado | `handoffs/H8-button.md` | `912e9a7` |
| H9 | Watchdog `sd_notify` | P3 | ✅ completado (validación en Pi pendiente) | `handoffs/H9.md` | `5381ceb` |

Leyenda de estado: ⏳ pendiente · 🟡 en curso · ✅ completado · ⛔ bloqueado

## Decisiones registradas

| # | Decisión | Workstream | Fecha |
|---|---|---|---|
| 1 | La puerta de calidad está verde (baseline) antes de tocar nada | Global | 2026-08-20 |
| 2 | Modelo unificado: en `protected`, mutadores HMI (REST + WS no-loopback) exigen `X-API-Key`; `/admin/*` exige key siempre | H1 | 2026-08-20 |
| 3 | Dos dependencias en `deps.py`: `require_admin_api_key` y `require_admin_api_key_always` | H1 | 2026-08-20 |
| 4 | WS: exención de loopback (`127.0.0.1`/`::1`/`localhost`) para el display local; rechazo 4401 sin `accept()` | H1 | 2026-08-20 |
| 5 | `Screen.allow_mock_fallback` default → `False`; producción nunca cae a mock | H2 | 2026-08-20 |
| 6 | Touch: límites ABS reales vía `EVIOCGABS` (fcntl diferido, fallback `RAW_MAX=4096`) + `invert_x/y` aplicados | H2 | 2026-08-20 |
| 7 | `bandit` usa `--severity-level medium`; B104 (bind 0.0.0.0) y B601 (paramiko exec_command) suprimidos con `# nosec` por ser decisiones documentadas en `docs/SECURITY.md` | H4 | 2026-08-20 |
| 8 | `/32` en ethernet queda rechazado por la validación de red (IP=red=broadcast); política revisable | H3 | 2026-08-20 |
| 9 | `RPI_HOST` sin default: los scripts de deploy exigen `RPI_HOST` en `.env` (eliminada IP hardcodeada `192.168.88.211`) | H6 | 2026-08-20 |
| 10 | Deploy usa `{VENV_PY} -m pip` (eliminada dependencia del binario `pip3`) | H6 | 2026-08-20 |
| 11 | `startup_policy` default = `restore` (conserva comportamiento actual); `off`/`safe` opt-in para actuadores físicos futuros | H8 | 2026-08-20 |
| 12 | Watchdog `sd_notify` 100% stdlib (AF_UNIX con fallback si no existe en Windows); `Type=notify` + `WatchdogSec=30`; no-op sin systemd | H9 | 2026-08-20 |
| 13 | Tests HIL marcados `@pytest.mark.hardware`, auto-skip salvo `RPI_HIL=1`; marker registrado en ambos `pyproject.toml` | H6 | 2026-08-20 |
| 14 | **H7 diferido:** no separar HMI runtime de Admin service ahora (recomendación de la auditoría externa). Documentado como decisión; revisable al crecer la superficie admin | H7 | 2026-08-20 |
| 15 | **Botón = toggle LED:** cada pulsación alterna el LED (vía `toggle_led()` atómico) e incrementa el contador. UI renombrada a "TOGGLE LED"/"ALTERNAR" | H8-button | 2026-08-20 |
| 16 | **UI web sin `X-API-Key`:** diferido. En `protected`, la UI web desde LAN queda read-only (el display local por loopback y scripts/curl con header sí funcionan). Documentado como limitación conocida | UI | 2026-08-20 |

## Gates

| Gate | Criterio | Estado |
|---|---|---|
| D1 (tras H1) | `pytest backend/tests/` + `mypy` + `ruff` verdes | ✅ (287 passed / 4 skipped) |
| D2 (tras H2+H3+H4+H5) | pytest (backend+display) + mypy + ruff + vitest + build verdes | ✅ (303 passed / 4 skipped · mypy 0 · ruff 0 · vitest 16/16 · build OK) |
| D3 (tras H4) | checks nuevos de `ci.yml` reproducibles localmente (bandit 0 medium+, pip-audit/npm audit en CI) | ✅ (bandit exit 0) |
| D2/D3 (tras H6+H8+H9) | pytest (backend+display) + mypy + ruff verdes | ✅ (315 passed / 9 skipped · mypy 0 · ruff 0) |
| D2/D3 (tras H8-button) | pytest (backend+display) + mypy + ruff + vitest + build verdes | ✅ (318 passed / 9 skipped · mypy 0 · ruff 0 · vitest 16/16 · build OK) |
| D4 (tras H6) | servicios vivos en la Pi + HIL + runbook firmado | ⏳ (HW) |

## Log de ejecución

- 2026-08-20 — FASE FINAL iniciada. Baseline registrado (pytest 278/4/0 · mypy 0 · ruff 0 · vitest 16/16 · build OK).
- 2026-08-20 — `docs/deploy/INICIO.md` reescrito incorporando la 2ª auditoría externa (P0-P3, H1-H8, D1-D4).
- 2026-08-20 — H1 ✅ (auth REST+WS unificada). Gate D1 verde.
- 2026-08-20 — H2 ∥ H3 ∥ H4 ∥ H5 ✅ en paralelo. Gate D2+D3 verde.
- 2026-08-20 — Commits H1–H5: `1c5bcf1` · `2de825c` · `e6170de` · `d8ff3dd` · `0802149` · `c2a3db1`.
- 2026-08-20 — H6-deploy ∥ H6-hil ∥ H8 ∥ H9 ✅ en paralelo. Gate D2/D3 verde (315 passed / 9 skipped · mypy 0 · ruff 0).
- 2026-08-20 — Commits H6–H9: `8203970`(H6-deploy) · `64bbf14`(H8) · `5381ceb`(H9) · `92fa837`(H6-hil) · `52f46c4`(runbook).
- 2026-08-20 — Decisiones de producto H7/H8/UI registradas. H8-button ✅ (botón = toggle LED). Commit `912e9a7`. Gate D2/D3 verde (318 passed / 9 skipped · mypy 0 · ruff 0 · vitest 16/16 · build OK).

## Pendientes tras esta fase (para la Pi o decisión de usuario)

- **H6 (hardware, ejecución real en la Pi):** instalar sudoers, crear `.env` de producción, `systemd-analyze verify`, decidir `/dev/mem`, correr smoke (401/200) y HIL, firmar el runbook. Todo documentado en `docs/deploy/runbook.md`.
- **H7:** separar HMI runtime de Admin service (`:8001` + firewall) — diferido por decisión de producto (n.º 14). Revisable al crecer la superficie admin.
- **H9 (validación en Pi):** confirmar que `Type=notify` + `WatchdogSec=30` no producen falsos reinicios bajo carga real.
- **UI web auth:** añadir un mecanismo en el cliente web para enviar `X-API-Key` (WS y REST) — diferido por decisión de producto (n.º 16).
