# v0.4.0 — Refactor de seguridad + cierre HIL en Pi real

## Resumen

Release de la Fase 8: refactor de seguridad del panel web y cierre de la
validación HIL (Hardware-In-the-Loop) sobre Raspberry Pi física.

## Cambios clave

- `feat(security)` — gestión de contraseña del panel web (default `1234`).
- `feat(security)` — contraseña **desactivada por defecto** (`SECURITY_MODE=local`) + GPIO20/21 + display.
- `feat(ui)` — interruptor ON/OFF, pulsador y título LED estático.
- `fix(security)` — **fail-closed** ante fallo de SQLite en arranque (el backend no entra en READY).
- `refactor(security)` — elimina `SECURITY_MODE` legacy y corrige el contrato de login.
- `fix(ui)` — corrige ortografía de "contraseña" con Ñ.
- `chore(hil)` — cierre HIL en Pi real: tests extendidos + runbook.

## Verificación

- `pytest backend/tests display/tests`: **393 passed, 9 skipped**.
- HIL en Pi real (RPi 1 Model B+, ARMv6):
  - Existentes (`test_hil_hardware.py`): **5/5 passed**.
  - Extendidos (`test_hil_hardware_extended.py`): **6/6 passed**.
- `ruff` / `mypy` / `vitest` (27 passed) / `npm audit` (0 vuln) / `bandit` (sin issues medium+) / `pip-audit` (sin vuln): verdes.
- Smoke post-deploy en Pi: `VERSION=0.4.0`, `/health` y `/health/ready` → `200`, servicios `active active`, `NRestarts=0`.

## Pendientes fuera de alcance automatizado (requieren acción física/manual)

- Apagado brusco (corte de alimentación) y corrupción de la SQLite viva: procedimientos en `docs/deploy/handoffs/HIL_0.4.0_RUNBOOK.md` (§4).
- Login/logout con panel protegido (401 tras logout) solo es demostrable activando la contraseña desde la UI.

## Documentación

- `docs/deploy/handoffs/HIL_0.4.0_RUNBOOK.md` — runbook HIL v0.4.0.
- `docs/deploy/handoffs/FASE8_F6_CIERRE.md` — cierre del refactor 0.4.0.
