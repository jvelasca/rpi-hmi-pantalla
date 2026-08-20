# Estado Global del Despliegue y Cierre de la FASE FINAL

> **ÚNICO editor de este archivo: el hilo principal.**
> Los subagentes escriben en `docs/deploy/handoffs/<ws-id>.md` y devuelven su resumen; jamás editan aquí.

## Estado general

- **Fase actual:** FASE FINAL — código cerrado (H1–H5); queda **H6 (hardware)** y decisiones **H7/H8**.
- **Última actualización:** 2026-08-20
- **Commit base (restauración):** `d16f991` (HEAD actual `c2a3db1`)
- **Baseline puerta de calidad:** pytest = 278 passed / 4 skipped · mypy = 0 · ruff = 0 · vitest = 16/16 · build OK

## Workstreams

| ID | Nombre | Prioridad | Estado | Handoff | Commit |
|---|---|---|---|---|---|
| H1 | Unificar auth REST+WS (seguridad) | P1 | ✅ completado | `handoffs/H1.md` | `1c5bcf1` |
| H2 | Display + touch | P1/P2/P3 | ✅ completado | `handoffs/H2.md` | `e6170de` |
| H3 | Red (validación) | P2 | ✅ completado | `handoffs/H3.md` | `d8ff3dd` |
| H4 | CI/CD + dependencias | P2 | ✅ completado | `handoffs/H4.md` | `0802149` |
| H5 | Docs/versión | P2/P3 | ✅ completado | `handoffs/H5.md` | `c2a3db1` |
| H6 | Despliegue a la Pi (runbook) | P0 | ⏳ pendiente (requiere HW) | — | — |
| H7 | Arquitectura mayor (HMI vs Admin) | P3 | ⛔ bloqueado (decisión usuario) | — | — |
| H8 | Decisiones de producto | P3 | ⛔ bloqueado (decisión usuario) | — | — |

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

## Gates

| Gate | Criterio | Estado |
|---|---|---|
| D1 (tras H1) | `pytest backend/tests/` + `mypy` + `ruff` verdes | ✅ (287 passed / 4 skipped) |
| D2 (tras H2+H3+H4+H5) | pytest (backend+display) + mypy + ruff + vitest + build verdes | ✅ (303 passed / 4 skipped · mypy 0 · ruff 0 · vitest 16/16 · build OK) |
| D3 (tras H4) | checks nuevos de `ci.yml` reproducibles localmente (bandit 0 medium+, pip-audit/npm audit en CI) | ✅ (bandit exit 0) |
| D4 (tras H6) | servicios vivos en la Pi + HIL + runbook | ⏳ (HW) |

## Log de ejecución

- 2026-08-20 — FASE FINAL iniciada. Baseline registrado (pytest 278/4/0 · mypy 0 · ruff 0 · vitest 16/16 · build OK).
- 2026-08-20 — `docs/deploy/INICIO.md` reescrito incorporando la 2ª auditoría externa (P0-P3, H1-H8, D1-D4).
- 2026-08-20 — H1 ✅ (auth REST+WS unificada). Gate D1 verde.
- 2026-08-20 — H2 ∥ H3 ∥ H4 ∥ H5 ✅ en paralelo. Gate D2+D3 verde.
- 2026-08-20 — Commits: `1c5bcf1`(H1) · `2de825c`(docs) · `e6170de`(H2) · `d8ff3dd`(H3) · `0802149`(H4) · `c2a3db1`(H5).

## Pendientes tras esta fase (para H6/H7/H8 o auditoría futura)

- **H6 (hardware, requiere Pi):** sudoers, `.env` de producción, `VENV_PIP`, límites systemd, `/dev/mem`, smoke de endpoints protegidos, HIL, `docs/deploy/runbook.md`.
- **H7:** separar HMI runtime de Admin service (`:8001` + firewall).
- **H8:** `startup_policy: off/restore/safe` para futuros actuadores; semántica del botón.
- **P3-5:** watchdog `sd_notify` (`READY=1`/`WATCHDOG=1`) + `Type=notify` + `WatchdogSec=30`.
- **P3-6:** tests HIL (`@pytest.mark.hardware`).
- **Observación de producto:** el frontend web no tiene aún UI para enviar `X-API-Key` (ni por WS desde un navegador LAN ni por REST). En `protected`, el display local (loopback) y herramientas con header (curl/scripts) funcionan; la UI web desde LAN queda read-only hasta añadir un mecanismo de auth en el cliente.
