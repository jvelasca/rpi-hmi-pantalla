# FASE 3 — Limpieza de código obsoleto — CIERRE

- Rama/base: `main` @ `881ec1a` (working tree con Fases 1-2 sin commit)
- Versión: 0.3.1
- Resumen: borrado definitivo de `legacy/`, `Rpi_Pantalla_V1.py`, tests raíz y
  scripts de deploy duplicados; archivado de scripts one-off y handoffs/auditorías
  históricos a `docs/archive/`; actualizadas las referencias vivas en runbook,
  README y CONTEXT. Sin commits git.

## Cambios

### BORRADOS (`git rm`, 12 archivos)

- `legacy/README.md`, `legacy/fb_probe.py`, `legacy/fb_ui.py`, `legacy/hal.py`,
  `legacy/pi_hmi_server.py`, `legacy/static/index.html` (carpeta `legacy/` completa)
- `Rpi_Pantalla_V1.py` (wrapper suelto que delegaba en `backend.app.main`)
- `tests/test_fb_ui.py`, `tests/__init__.py` (solo testeaban `legacy/fb_ui.py`;
  el directorio raíz `tests/` queda vacío)
- `scripts/deploy_frontend.py`, `scripts/deploy_step.py`, `scripts/rollback.py`
  (deploy duplicados; el `--rollback` real vive en `scripts/deploy_atomic.py`)

### ARCHIVADOS (`git mv`, 63 archivos → `docs/archive/`)

- Raíz (1): `PROMPT_CONTINUACION.md` → `docs/archive/`
- Scripts one-off (15) → `docs/archive/scripts/`:
  `display_probe.py`, `ili9486_driver.py`, `post_reboot_check.py`,
  `configure_display.ps1`, `configure_display_direct.ps1`, `connect_and_test.ps1`,
  `find_and_connect.ps1`, `full_deploy.ps1`, `run_configurar_pantalla.ps1`,
  `run_diagnostico.ps1`, `setup_display.sh`, `setup_venv.sh`, `ili9486-drm.dts`,
  `spidev0.dts`, `touch-fix.dts`
- Handoffs CHAT (10) → `docs/archive/handoffs/`
- Auditorías (21) → `docs/archive/audits/`:
  `fase0-seguridad.md` … `fase6-persistencia.md`, `fase3.5-correccion.md`,
  `plan-consolidado.md`, y `refactor/` (ESTADO, PLAN_REFACTOR, PROMPTS_SUBAGENTES,
  handoffs A1…G + _PLANTILLA)
- Handoffs de deploy históricos (16) → `docs/archive/deploy-handoffs/`:
  `H1.md`…`H9.md` (incl. `H6-deploy.md`, `H6-hil.md`, `H8-button.md`) y
  `RS_A…RS_SECURITY_AUDIT.md`

### REFERENCIAS ACTUALIZADAS

- `docs/deploy/runbook.md` — 3 referencias a handoffs reubicados en
  `docs/archive/deploy-handoffs/` (H9, H6-hil, H6-deploy/H8/H9).
- `README.md` — árbol de `scripts/`: retirado `deploy_frontend.py`, reflejado
  `deploy.py` + `deploy_atomic.py` + `start_hmi.sh` + `setup_rpi.sh`.
- `docs/CONTEXT.md` — sección "Despliegue" del frontend: `deploy_frontend.py` →
  `deploy.py` (build+sync unificado).

## Verificación

- **pytest** `python -m pytest backend/tests/ display/tests/ -q`:
  **346 passed / 9 skipped / 5 warnings** (84.55 s) — verde.
- **ruff** `python -m ruff check backend/ display/ scripts/ --config backend/pyproject.toml`:
  **All checks passed!** — verde (los one-off que podían fallar ruff quedaron
  fuera de `scripts/` al archivarse).
- **release-smoke (simulado sobre estado trackeado)**:
  - Existen: `VERSION`, `backend/app/main.py`, `backend/config/devices.yaml`,
    `display/app.py`, `config/systemd/rpi-hmi-backend.service`,
    `config/systemd/rpi-hmi-display.service` → **6/6 OK**.
  - `VERSION = 0.3.1` (semver válido).
  - Prohibidos (`__pycache__`, `*.pyc`, `.env`) en `git ls-files` → **0**.
- **git status** final sin artefactos (`__pycache__`, `.pyc`, `.pytest_cache`,
  `.ruff_cache`): correcto (ignorados por `.gitignore`). Queda un `.env` local
  gitignored (secreto de desarrollo, no se toca).

## Decisiones

1. **`deploy_atomic.py` se CONSERVA.** `docs/PLAN_CIERRE_V1.md` §3 sugería
   "retirar `deploy_atomic.py`", pero el handoff de entrada (fuente de verdad de
   esta fase) lo marca KEEP y `runbook.md` §5.1/§5.2 lo recomienda. Se siguió el
   handoff.
2. **Deploy duplicados → borrar; one-off de diagnóstico → archivar.** Según la
   regla del handoff: el usuario aprobó borrar `legacy/` y scripts duplicados;
   los one-off con posible valor histórico se archivaron.
3. **`PROMPT_CONTINUACION.md` → archivar** (superado por `docs/CONTEXT.md`;
   describía la arquitectura `pi_hmi_server.py`+`fb_ui.py` ya eliminada).
4. **`.pyproj`/`.slnx` NO se tocan** (fuera de las listas del handoff; ver
   pendientes).

## Pendientes / fuera de alcance

- **`Rpi_Pantalla_V1.pyproj` + `Rpi_Pantalla_V1.slnx`**: scaffolding de Visual
  Studio obsoleto que referencia `Rpi_Pantalla_V1.py` (ya borrado) y
  `backend/app/hardware/hal.py` (no existe). No están en las listas del handoff;
  se dejaron intactos. Recomendado borrar/archivar con aprobación del usuario.
- **`docs/ARCHITECTURE.md`** (NO-tocar, fuera del alcance de actualización): su
  árbol de `scripts/` (líneas ~196-198) aún lista `deploy_step.py`,
  `deploy_frontend.py`, `rollback.py`. Recomendado corregir en Fase 4.
- **`pyproject.toml` (raíz)**: `norecursedirs` aún contiene `"legacy"` (ya no
  existe; inofensivo). NO-tocar.
- **`docs/CONTEXT.md`** "Estructura de la Pi" aún menciona `pi_hmi_server.py` /
  `fb_ui.py` como "LEGACY - detenido" (nota histórica ya obsoleta).
- **`QUICKSTART.md`**: desactualizado (referencia `backend/app/hardware/hal.py`,
  `domain/`, `devices.py` inexistentes; solapa README/runbook). Está en NO-tocar;
  recomendado revisar en Fase 4.
- **`docs/PLAN_FASE2.md`**: plan histórico no listado; se dejó intacto.
- **Fases 4/5 detectadas y NO tocadas**: rate-limiting de login (F4), verificación
  `.gitattributes`/sudoers (F4), resolución display `480x320` hardcodeada (F4),
  bump a `0.3.2` (F5).

## TEXTO DE PASO (pegar en el siguiente chat)

"Proyecto RPi HMI en `main` @ `881ec1a` (working tree, sin commit). Fase 3
(limpieza de código obsoleto) completada: borrados 12 archivos con `git rm`
(`legacy/` completo, `Rpi_Pantalla_V1.py`, `tests/test_fb_ui.py`+`__init__.py`,
`scripts/deploy_frontend.py`/`deploy_step.py`/`rollback.py`) y archivados 63 con
`git mv` a `docs/archive/` (scripts one-off, handoffs CHAT, auditorías, handoffs
H/RS históricos). Actualizadas referencias en runbook/README/CONTEXT. Verificación:
pytest 346 passed / 9 skipped · ruff 'All checks passed!' · release-smoke 6/6
archivos + VERSION=0.3.1 + 0 prohibidos en git. Pendientes: `.pyproj`/`.slnx`
obsoletos, árbol de scripts en ARCHITECTURE.md, `norecursedirs` con 'legacy',
QUICKSTART desactualizado. Siguiente fase: Fase 4 — hardening (rate-limiting login,
resolución display, `.gitattributes`/sudoers). Lee `docs/deploy/handoffs/FASE3_LIMPIEZA_CIERRE.md`."
